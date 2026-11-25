"""
VOXEN DATABASE ENGINE - SQLITE WAL ARCHITECTURE
Wysokowydajny silnik relacyjnej bazy danych SQLite zoptymalizowany dla komunikatora.
Cechy:
- Tryb WAL (Write-Ahead Logging) dla współbieżnych odczytów i zapisów bez blokowania.
- Wymuszenie kluczy obcych (foreign keys) i indeksowanie zapytań.
- Automatyczna migracja istniejących danych z users.json z bezpiecznym haszowaniem haseł.
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
import sqlite3
import threading
from typing import Any, Dict, Optional, Tuple

from security.crypto import PasswordHasher
from security.session import SessionManager

logger = logging.getLogger("Voxen.Database")


class DatabaseManager:
    """Zarządca bazy danych SQLite Voxen"""

    DEFAULT_DB_PATH = "voxen.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or self.DEFAULT_DB_PATH)
        self._lock = threading.Lock()
        self._init_db()
        self._migrate_from_json_if_needed()
        self._seed_initial_messages_if_empty()
        self._seed_initial_servers_and_channels_if_empty()

    def _get_connection(self) -> sqlite3.Connection:
        """Tworzy połączenie ze skonfigurowanymi pragmami wydajnościowymi"""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row

        # Konfiguracja SQLite dla wysokiej wydajności (WAL Mode)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _init_db(self) -> None:
        """Tworzy tabele i indeksy bazy danych"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Tabela użytkowników
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    security INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'online',
                    custom_status TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_login TEXT
                );
            """)

            # Migracja kolumn status i custom_status jeśli brak w tabeli users
            cursor.execute("PRAGMA table_info(users);")
            user_cols = [col[1] for col in cursor.fetchall()]
            if "status" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'online';")
            if "custom_status" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN custom_status TEXT DEFAULT '';")

            # Tabela sesji
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                );
            """)

            # Tabela historii wiadomości czatu (Trwałość w SQLite WAL)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    packet_id TEXT UNIQUE,
                    sender TEXT NOT NULL COLLATE NOCASE,
                    target TEXT NOT NULL COLLATE NOCASE,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_dm INTEGER DEFAULT 1,
                    is_read INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );
            """)

            # Migracja kolumny is_read jeśli brak w istniejącej tabeli
            cursor.execute("PRAGMA table_info(messages);")
            cols = [col[1] for col in cursor.fetchall()]
            if "is_read" not in cols:
                cursor.execute("ALTER TABLE messages ADD COLUMN is_read INTEGER DEFAULT 1;")

            # Tabela serwerów
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    icon TEXT NOT NULL,
                    owner_id INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );
            """)

            # Tabela kanałów
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    topic TEXT DEFAULT '',
                    channel_type TEXT DEFAULT 'text',
                    position INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(server_id, name)
                );
            """)

            # Chat file and image attachments
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    thumbnail_path TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("PRAGMA table_info(attachments);")
            attachment_cols = [col[1] for col in cursor.fetchall()]
            if "thumbnail_path" not in attachment_cols:
                cursor.execute("ALTER TABLE attachments ADD COLUMN thumbnail_path TEXT;")

            # Indeksy
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_target ON messages(target);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender, target);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(target, is_read);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_server ON channels(server_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);")

            conn.commit()

    def _migrate_from_json_if_needed(self, json_path: str = "users.json") -> None:
        """
        Automatyczna migracja z users.json do SQLite.
        Pobiera użytkowników, haszuje plain-text hasła za pomocą scrypt i zapisuje w SQLite.
        """
        file_path = Path(json_path)
        if not file_path.exists():
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_users = data.get("users", [])
            if not raw_users:
                return

            migrated_count = 0
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()

                for raw_user in raw_users:
                    email = raw_user.get("email", "").strip()
                    plain_pass = raw_user.get("password", "")
                    security = raw_user.get("security", 1)
                    last_login = raw_user.get("last_login")

                    if not email or not plain_pass:
                        continue

                    # Sprawdź czy już istnieje w SQLite
                    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                    if cursor.fetchone():
                        continue

                    # Wygeneruj bezpieczny hasz scrypt
                    password_hash = PasswordHasher.hash_password(plain_pass)
                    username = email.split("@")[0]
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    cursor.execute("""
                        INSERT INTO users (email, username, password_hash, security, created_at, last_login)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (email, username, password_hash, security, now_str, last_login))

                    migrated_count += 1

                conn.commit()

            if migrated_count > 0:
                print(f"📦 Bezpiecznie zmigrowano {migrated_count} kont z users.json do SQLite (scrypt hashed)!")
                # Zmiana nazwy pliku na backup
                backup_path = file_path.with_suffix(".json.migrated")
                try:
                    file_path.rename(backup_path)
                    print(f"📁 Zarchiwizowano stary plik jako: {backup_path.name}")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Błąd podczas migracji z JSON do SQLite: {e}")

    # ==========================================
    # ZARZĄDZANIE UŻYTKOWNIKAMI
    # ==========================================

    def create_user(
        self,
        email: str,
        password: str,
        username: Optional[str] = None,
        security: int = 1
    ) -> Tuple[bool, str | Dict[str, Any]]:
        """Tworzy nowego użytkownika z haszowanym hasłem"""
        email = email.strip()
        if not email or not password:
            return False, "Email i hasło są wymagane!"

        if "@" not in email:
            return False, "Niepoprawny format adresu email!"

        if len(password) < 6:
            return False, "Hasło musi mieć co najmniej 6 znaków!"

        uname = username or email.split("@")[0]
        hashed_password = PasswordHasher.hash_password(password)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (email, username, password_hash, security, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (email, uname, hashed_password, security, now_str))
                user_id = cursor.lastrowid
                conn.commit()

                user_data = {
                    "id": user_id,
                    "email": email,
                    "username": uname,
                    "security": security,
                    "created_at": now_str,
                    "last_login": None
                }
                return True, user_data

        except sqlite3.IntegrityError:
            return False, "Użytkownik o podanym adresie email już istnieje!"
        except Exception as e:
            return False, f"Błąd bazy danych: {e}"

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Pobiera rekord użytkownika po adresie email"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email.strip(),))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_last_login(self, email: str) -> None:
        """Aktualizuje datę ostatniego logowania"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login = ? WHERE email = ?", (now_str, email.strip()))
            conn.commit()

    def update_user_status(self, user_id_or_email: int | str, status: str, custom_status: str = "") -> bool:
        """
        Aktualizuje status obecności użytkownika (online, idle, dnd, offline) oraz opcjonalny status tekstowy.
        """
        status_clean = status.lower().strip()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(user_id_or_email, int) or (isinstance(user_id_or_email, str) and user_id_or_email.isdigit()):
                cursor.execute("""
                    UPDATE users SET status = ?, custom_status = ? WHERE id = ?
                """, (status_clean, custom_status.strip(), int(user_id_or_email)))
            else:
                cursor.execute("""
                    UPDATE users SET status = ?, custom_status = ? WHERE email = ? OR username = ?
                """, (status_clean, custom_status.strip(), str(user_id_or_email).strip(), str(user_id_or_email).strip()))
            conn.commit()
            return cursor.rowcount > 0

    def get_user_status(self, user_id_or_email: int | str) -> Dict[str, str]:
        """Pobiera status obecności i własny tekst statusu użytkownika"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(user_id_or_email, int) or (isinstance(user_id_or_email, str) and user_id_or_email.isdigit()):
                cursor.execute("SELECT status, custom_status FROM users WHERE id = ?", (int(user_id_or_email),))
            else:
                cursor.execute("SELECT status, custom_status FROM users WHERE email = ? OR username = ?", (str(user_id_or_email).strip(), str(user_id_or_email).strip()))
            row = cursor.fetchone()
            if row:
                return {
                    "status": row["status"] or "online",
                    "custom_status": row["custom_status"] or ""
                }
            return {"status": "online", "custom_status": ""}

    # ==========================================
    # ZARZĄDZANIE SESJAMI (PERSISTENCY)
    # ==========================================

    def create_session(self, user_id: int, duration_days: int = 30) -> str:
        """Tworzy nową unikalną sesję dla użytkownika"""
        token = SessionManager.generate_token()
        now = datetime.now()
        expires = now + timedelta(days=duration_days)

        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        expires_str = expires.strftime("%Y-%m-%d %H:%M:%S")

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (token, user_id, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (token, user_id, now_str, expires_str))
            conn.commit()

        return token

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Weryfikuje token sesji i zwraca dane użytkownika jeśli aktywna i nie wygasła"""
        if not token:
            return None

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.email, u.username, u.security, u.last_login
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.is_active = 1 AND s.expires_at > ?
            """, (token, now_str))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def revoke_session(self, token: str) -> None:
        """Dezaktywuje sesję (wylogowanie)"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE sessions SET is_active = 0 WHERE token = ?", (token,))
            conn.commit()

    # ==========================================
    # HISTORIA WIADOMOŚCI CZATU (SQLITE PERSISTENCE)
    # ==========================================

    def _seed_initial_messages_if_empty(self) -> None:
        """Wstawia początkowe wiadomości dla demonstracji, jeśli baza jest pusta"""
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages")
                count = cursor.fetchone()[0]
                if count == 0:
                    now = datetime.now()
                    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                    time_str = now.strftime("%H:%M")

                    seeds = [
                        ("Unity Bot", "Direct Messages", "Witaj w Voxen! Silnik sieciowy i baza SQLite działają poprawnie. Napisz cokolwiek!", time_str, now_str),
                        ("Unity Bot", "admin", "Siema! Wszystkie pakiety są zapisywane trwale w SQLite w trybie WAL.", time_str, now_str),
                        ("Wincekk", "admin", "Siemanko! Sprawdzałeś już nowy Virtual Scrolling? Przewijanie jest niesamowicie płynne!", time_str, now_str),
                        ("Nemeczek", "admin", "Cześć! Kiedy odpalamy serwer gier?", time_str, now_str),
                    ]
                    for sender, target, content, t_str, dt_str in seeds:
                        cursor.execute("""
                            INSERT INTO messages (sender, target, content, timestamp, is_dm, created_at)
                            VALUES (?, ?, ?, ?, 1, ?)
                        """, (sender, target, content, t_str, dt_str))
                    conn.commit()
        except Exception as e:
            logger.error(f"Błąd inicjalizacji domyślnych wiadomości: {e}")

    def save_message(
        self,
        sender: str,
        target: str,
        content: str,
        packet_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        is_dm: bool = True,
        is_read: bool = True
    ) -> int:
        """
        Trwale zapisuje wiadomość w bazie SQLite z oznaczeniem przeczytania.
        Zwraca ID wstawionego rekordu.
        """
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        time_str = timestamp or now.strftime("%H:%M")

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO messages (packet_id, sender, target, content, timestamp, is_dm, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (packet_id, sender.strip(), target.strip(), content, time_str, 1 if is_dm else 0, 1 if is_read else 0, now_str))
            conn.commit()
            return cursor.lastrowid or 0

    def mark_as_read(self, conversation: str, current_user: str) -> int:
        """
        Oznacza wiadomości w danej konwersacji lub kanale jako przeczytane.
        Zwraca liczbę oznaczonych wiadomości.
        """
        conv = conversation.strip()
        user = current_user.strip()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE messages
                SET is_read = 1
                WHERE is_read = 0 AND (
                    (sender = ? AND (target = ? OR target = 'Direct Messages'))
                    OR (target = ?)
                    OR (target = ? AND sender != ?)
                )
            """, (conv, user, conv, conv, user))
            updated = cursor.rowcount
            conn.commit()
            return updated

    def get_unread_count(self, conversation: str, current_user: str) -> int:
        """Zwraca liczbę nieprzeczytanych wiadomości dla danej konwersacji lub kanału"""
        conv = conversation.strip()
        user = current_user.strip()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM messages
                WHERE is_read = 0 AND (
                    (sender = ? AND (target = ? OR target = 'Direct Messages'))
                    OR (target = ? AND sender != ?)
                )
            """, (conv, user, conv, user))
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_all_unread_counts(self, current_user: str) -> Dict[str, int]:
        """
        Zwraca słownik nieprzeczytanych wiadomości:
        Dla DMs: klucz to nazwa nadawcy (np. 'Unity Bot': 2)
        Dla kanałów: klucz to 'Serwer#kanał' lub nazwa kanału
        """
        user = current_user.strip()
        unread = {}
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # DMs
            cursor.execute("""
                SELECT sender, COUNT(*) as cnt
                FROM messages
                WHERE is_read = 0 AND is_dm = 1 AND sender != ?
                GROUP BY sender
            """, (user,))
            for row in cursor.fetchall():
                unread[row["sender"]] = row["cnt"]

            # Kanały serwerów
            cursor.execute("""
                SELECT target, COUNT(*) as cnt
                FROM messages
                WHERE is_read = 0 AND is_dm = 0 AND sender != ?
                GROUP BY target
            """, (user,))
            for row in cursor.fetchall():
                unread[row["target"]] = row["cnt"]

        return unread

    def get_conversation_history(
        self,
        conversation: str,
        current_user: str,
        limit: int = 200
    ) -> list:
        """
        Pobiera historię wiadomości dla danej konwersacji (DM lub kanał).
        Zwraca listę słowników posortowaną chronologicznie (od najstarszej do najnowszej).
        """
        conv = conversation.strip()
        user = current_user.strip()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # Pobieramy wiadomości wymienione między 'user' a 'conv',
            # lub wiadomości wysłane bezpośrednio do 'conv' (np. kanał lub Direct Messages ogólny)
            cursor.execute("""
                SELECT id, packet_id, sender, target, content, timestamp, is_dm, created_at
                FROM messages
                WHERE 
                    (sender = ? AND target = ?)
                    OR (sender = ? AND target = ?)
                    OR (target = ? AND is_dm = 0)
                    OR (target = 'Direct Messages' AND (sender = ? OR target = ?))
                    OR (sender = ? AND target = 'Direct Messages')
                ORDER BY id ASC
                LIMIT ?
            """, (user, conv, conv, user, conv, conv, conv, conv, limit))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                row_dict = dict(row)
                row_dict["is_own"] = (row_dict["sender"].lower() == user.lower())
                row_dict["is_bot"] = ("bot" in row_dict["sender"].lower())
                cursor.execute(
                    "SELECT * FROM attachments WHERE message_id = ? ORDER BY id ASC",
                    (row_dict["id"],)
                )
                row_dict["attachments"] = [dict(att) for att in cursor.fetchall()]
                result.append(row_dict)
            return result

    def clear_conversation_history(self, conversation: str, current_user: str) -> None:
        """Usuwa historię wiadomości dla danej pary rozmówców"""
        conv = conversation.strip()
        user = current_user.strip()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM messages
                WHERE (sender = ? AND target = ?) OR (sender = ? AND target = ?) OR (target = ?)
            """, (user, conv, conv, user, conv))
            conn.commit()

    # ==========================================
    # ZAŁĄCZNIKI WIADOMOŚCI
    # ==========================================

    def save_attachment(
        self,
        message_id: int,
        filename: str,
        original_name: str,
        file_type: str,
        file_size: int,
        mime_type: str,
        file_path: str,
        thumbnail_path: Optional[str] = None
    ) -> int:
        """Zapisuje metadane załącznika powiązanego z wiadomością."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attachments (
                    message_id, filename, original_name, file_type, file_size,
                    mime_type, file_path, thumbnail_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id, filename, original_name, file_type, file_size,
                mime_type, file_path, thumbnail_path, now_str
            ))
            conn.commit()
            return cursor.lastrowid

    def get_attachment(self, attachment_id: int) -> Optional[Dict[str, Any]]:
        """Pobiera jeden załącznik po jego ID."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_attachments(self, message_id: int) -> list:
        """Pobiera wszystkie załączniki dla wiadomości."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM attachments
                WHERE message_id = ?
                ORDER BY id ASC
            """, (message_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_message_attachments(self, message_id: int) -> list:
        """Alias dla get_attachments."""
        return self.get_attachments(message_id)

    def get_attachment_by_message(self, message_id: int) -> list:
        """Alias dla get_attachments."""
        return self.get_attachments(message_id)

    def create_attachment(self, **attachment_data: Any) -> int:
        """Alias dla save_attachment accepting a metadata dictionary."""
        return self.save_attachment(
            message_id=attachment_data["message_id"],
            filename=attachment_data["filename"],
            original_name=attachment_data["original_name"],
            file_type=attachment_data["file_type"],
            file_size=attachment_data["file_size"],
            mime_type=attachment_data["mime_type"],
            file_path=attachment_data["file_path"],
            thumbnail_path=attachment_data.get("thumbnail_path")
        )

    def delete_attachment(self, attachment_id: int) -> bool:
        """Usuwa metadane załącznika."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ==========================================
    # SERWERY I KANAŁY TEKSTOWE (SQLITE)
    # ==========================================

    def _seed_initial_servers_and_channels_if_empty(self) -> None:
        """Wstawia początkowe serwery i kanały jeśli baza jest pusta"""
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM servers")
                count = cursor.fetchone()[0]
                if count == 0:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    initial_servers = [
                        ("Voxen Official", "assets/images/logo.ico", [
                            ("ogólny", "Główny kanał społeczności Voxen"),
                            ("ogłoszenia", "Ważne aktualizacje i roadmapa projektu"),
                            ("pomoc", "Wsparcie techniczne i feedback")
                        ]),
                        ("Gaming", "🎮", [
                            ("gry-pc", "Rozmowy o grach komputerowych"),
                            ("konsole", "PlayStation, Xbox, Nintendo"),
                            ("szukam-ekipy", "Znajdź graczy do wspólnej gry")
                        ]),
                        ("Coding", "💻", [
                            ("python", "Architektura aplikacji i biblioteki"),
                            ("cpp-engine", "Optymalizacja silnika i sieci"),
                            ("projekty", "Prezentacja własnych projektów")
                        ]),
                        ("Music", "🎵", [
                            ("ulubione-kawałki", "Podziel się dobrą muzyką"),
                            ("twórczość", "Produkcja muzyczna i bity")
                        ]),
                        ("Art", "🎨", [
                            ("grafika", "Design UI/UX i concept art"),
                            ("animacje", "Showcase animacji")
                        ])
                    ]

                    for s_name, icon, channels in initial_servers:
                        cursor.execute("""
                            INSERT INTO servers (name, icon, owner_id, created_at)
                            VALUES (?, ?, 1, ?)
                        """, (s_name, icon, now_str))
                        s_id = cursor.lastrowid
                        pos = 0
                        for c_name, topic in channels:
                            cursor.execute("""
                                INSERT INTO channels (server_id, name, topic, channel_type, position, created_at)
                                VALUES (?, ?, ?, 'text', ?, ?)
                            """, (s_id, c_name, topic, pos, now_str))
                            pos += 1
                    conn.commit()
        except Exception as e:
            logger.error(f"Błąd inicjalizacji serwerów i kanałów: {e}")

    def get_servers(self) -> list:
        """Pobiera listę wszystkich dostępnych serwerów"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, icon, owner_id, created_at FROM servers ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def create_server(self, name: str, icon: str = "📁", owner_id: int = 1) -> tuple:
        """Tworzy nowy serwer i dodaje domyślny kanał #ogólny"""
        name = name.strip()
        if not name:
            return False, "Nazwa serwera nie może być pusta!"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO servers (name, icon, owner_id, created_at)
                    VALUES (?, ?, ?, ?)
                """, (name, icon, owner_id, now_str))
                server_id = cursor.lastrowid

                # Domyślny kanał ogólny
                cursor.execute("""
                    INSERT INTO channels (server_id, name, topic, channel_type, position, created_at)
                    VALUES (?, 'ogólny', 'Główny kanał serwera', 'text', 0, ?)
                """, (server_id, now_str))

                conn.commit()
                return True, {"id": server_id, "name": name, "icon": icon}
        except sqlite3.IntegrityError:
            return False, "Serwer o takiej nazwie już istnieje!"
        except Exception as e:
            return False, f"Błąd bazy danych: {e}"

    def delete_server(self, server_id: int) -> bool:
        """Usuwa serwer wraz ze wszystkimi kanałami (CASCADE)"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM servers WHERE id = ?", (server_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_channels(self, server_id: int) -> list:
        """Pobiera listę kanałów tekstowych dla danego serwera"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, server_id, name, topic, channel_type, position
                FROM channels
                WHERE server_id = ?
                ORDER BY position ASC, id ASC
            """, (server_id,))
            return [dict(row) for row in cursor.fetchall()]

    def create_channel(self, server_id: int, name: str, topic: str = "", channel_type: str = "text") -> tuple:
        """Tworzy nowy kanał w serwerze"""
        name = name.strip().lower().replace(" ", "-").replace("#", "")
        if not name:
            return False, "Nazwa kanału nie może być pusta!"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO channels (server_id, name, topic, channel_type, position, created_at)
                    VALUES (?, ?, ?, ?, 99, ?)
                """, (server_id, name, topic, channel_type, now_str))
                channel_id = cursor.lastrowid
                conn.commit()
                return True, {"id": channel_id, "server_id": server_id, "name": name, "topic": topic}
        except sqlite3.IntegrityError:
            return False, "Taki kanał już istnieje na tym serwerze!"
        except Exception as e:
            return False, f"Błąd bazy danych: {e}"

    def delete_channel(self, channel_id: int) -> bool:
        """Usuwa kanał z bazy danych"""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
            conn.commit()
            return cursor.rowcount > 0
