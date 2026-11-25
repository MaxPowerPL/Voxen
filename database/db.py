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
import hmac
import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from security.crypto import PasswordHasher
from security.session import SessionManager

logger = logging.getLogger("Voxen.Database")


class DatabaseManager:
    """Zarządca bazy danych SQLite Voxen"""

    DEFAULT_DB_PATH = "voxen.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or self.DEFAULT_DB_PATH)
        self._lock = threading.RLock()
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pinned_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
                    conversation TEXT NOT NULL,
                    pinned_by TEXT NOT NULL,
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    position INTEGER DEFAULT 0,
                    collapsed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(server_id, name)
                );
            """)
            cursor.execute("PRAGMA table_info(channels);")
            channel_cols = [col[1] for col in cursor.fetchall()]
            if "category_id" not in channel_cols:
                cursor.execute("ALTER TABLE channels ADD COLUMN category_id INTEGER REFERENCES channel_categories(id) ON DELETE SET NULL;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                    user_name TEXT NOT NULL COLLATE NOCASE,
                    muted INTEGER DEFAULT 0,
                    deafened INTEGER DEFAULT 0,
                    connected_at TEXT NOT NULL,
                    UNIQUE(channel_id, user_name)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    allowed INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(channel_id, role, permission)
                );
            """)

            # Server membership and role permissions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role TEXT NOT NULL DEFAULT 'member',
                    created_at TEXT NOT NULL,
                    UNIQUE(server_id, user_id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS member_timeouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(server_id, user_id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS member_activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    actor_id INTEGER,
                    target_user_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    secret TEXT NOT NULL DEFAULT '',
                    events TEXT NOT NULL DEFAULT '*',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_id INTEGER NOT NULL REFERENCES server_webhooks(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    signature TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    created_at TEXT NOT NULL
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    user_name TEXT NOT NULL COLLATE NOCASE,
                    emoji TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(message_id, user_name, emoji)
                );
            """)

            # Indeksy
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_target ON messages(target);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender, target);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(target, is_read);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pinned_messages_conversation ON pinned_messages(conversation);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_server ON channels(server_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_category ON channels(category_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_categories_server ON channel_categories(server_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_voice_participants_channel ON voice_participants(channel_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_permissions_channel ON channel_permissions(channel_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_server_members_server ON server_members(server_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_server_members_user ON server_members(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_activity_server ON member_activity_logs(server_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_activity_created ON member_activity_logs(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_server_webhooks_server ON server_webhooks(server_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_reactions_message ON message_reactions(message_id);")

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
                row_dict["reactions"] = self.get_message_reactions(row_dict["id"])
                row_dict["is_pinned"] = self.is_message_pinned(row_dict["id"])
                row_dict["is_pinned"] = self.is_message_pinned(row_dict["id"])
                result.append(row_dict)
            return result

    def search_messages(
        self,
        conversation: str,
        current_user: str,
        query: str = "",
        sender: str = "",
        timestamp: str = "",
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 200
    ) -> list:
        """Searches a DM or channel by content, sender and timestamp."""
        conv = conversation.strip()
        user = current_user.strip()
        search_query = query.strip()
        sender_query = sender.strip()
        timestamp_query = timestamp.strip() or start_timestamp or start_time or ""
        end_query = end_timestamp or end_time or ""

        conditions = [
            "("
            "(sender = ? AND target = ?) "
            "OR (sender = ? AND target = ?) "
            "OR (target = ? AND is_dm = 0) "
            "OR (target = 'Direct Messages' AND (sender = ? OR target = ?)) "
            "OR (sender = ? AND target = 'Direct Messages')"
            ")"
        ]
        params: list[Any] = [user, conv, conv, user, conv, conv, conv, conv]

        if search_query:
            conditions.append("(content LIKE ? COLLATE NOCASE)")
            params.append(f"%{search_query}%")
        if sender_query:
            conditions.append("(sender LIKE ? COLLATE NOCASE)")
            params.append(f"%{sender_query}%")
        if timestamp_query:
            conditions.append("(timestamp LIKE ? OR created_at LIKE ?)")
            params.extend([f"%{timestamp_query}%", f"%{timestamp_query}%"])
        if end_query:
            conditions.append("(created_at <= ?)")
            params.append(end_query)

        sql = """
            SELECT id, packet_id, sender, target, content, timestamp, is_dm, created_at
            FROM messages
            WHERE {where}
            ORDER BY id ASC
            LIMIT ?
        """.format(where=" AND ".join(conditions))
        params.append(max(1, int(limit)))

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            result = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict["is_own"] = row_dict["sender"].lower() == user.lower()
                row_dict["is_bot"] = "bot" in row_dict["sender"].lower()
                cursor.execute(
                    "SELECT * FROM attachments WHERE message_id = ? ORDER BY id ASC",
                    (row_dict["id"],)
                )
                row_dict["attachments"] = [dict(att) for att in cursor.fetchall()]
                row_dict["reactions"] = self.get_message_reactions(row_dict["id"])
                result.append(row_dict)
            return result

    def search_conversation_history(
        self,
        conversation: str,
        current_user: str,
        query: str = "",
        sender: str = "",
        timestamp: str = "",
        limit: int = 200
    ) -> list:
        """Alias for search_messages."""
        return self.search_messages(
            conversation=conversation,
            current_user=current_user,
            query=query,
            sender=sender,
            timestamp=timestamp,
            limit=limit
        )

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

    def delete_message(self, message_id: int) -> bool:
        """Deletes a message and cascades attached metadata."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sender, target FROM messages WHERE id = ?", (message_id,))
            row = cursor.fetchone()
            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            conn.commit()
            return cursor.rowcount > 0

    def pin_message(
        self,
        message_id: int,
        conversation: str,
        pinned_by: str
    ) -> tuple:
        """Pins a message in a DM or channel."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM messages WHERE id = ?", (message_id,))
            if not cursor.fetchone():
                return False, "Nie znaleziono wiadomości."
            cursor.execute("""
                INSERT INTO pinned_messages (message_id, conversation, pinned_by, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    conversation = excluded.conversation,
                    pinned_by = excluded.pinned_by
            """, (message_id, conversation.strip(), pinned_by.strip(), now_str))
            conn.commit()
            return True, {
                "message_id": message_id,
                "conversation": conversation.strip(),
                "pinned_by": pinned_by.strip()
            }

    def unpin_message(self, message_id: int) -> bool:
        """Removes a pinned message."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pinned_messages WHERE message_id = ?", (message_id,))
            conn.commit()
            return cursor.rowcount > 0

    def is_message_pinned(self, message_id: int) -> bool:
        """Checks whether a message is pinned."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM pinned_messages WHERE message_id = ?", (message_id,))
            return cursor.fetchone() is not None

    def get_pinned_messages(self, conversation: str) -> list:
        """Returns pinned messages for a DM or channel."""
        conv = conversation.strip()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    m.id,
                    m.packet_id,
                    m.sender,
                    m.target,
                    m.content,
                    m.timestamp,
                    m.is_dm,
                    m.created_at,
                    pm.pinned_by,
                    pm.created_at AS pinned_at
                FROM pinned_messages pm
                JOIN messages m ON m.id = pm.message_id
                WHERE pm.conversation = ?
                ORDER BY pm.id DESC
            """, (conv,))
            result = []
            for row in cursor.fetchall():
                item = dict(row)
                item["is_pinned"] = True
                result.append(item)
            return result

    def timeout_server_member(
        self,
        server_id: int,
        user_id: int,
        expires_at: str
    ) -> bool:
        """Creates or updates a server-member timeout."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO member_timeouts (server_id, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(server_id, user_id) DO UPDATE SET expires_at = excluded.expires_at
            """, (server_id, user_id, expires_at, now_str))
            conn.commit()
            self.add_member_activity_log(
                server_id,
                None,
                "member_timeout",
                user_id,
                f"Timeout expires at {expires_at}"
            )
            return True

    def get_member_timeout(self, server_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Returns active timeout metadata, or None when expired."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM member_timeouts
                WHERE server_id = ? AND user_id = ?
            """, (server_id, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            if row["expires_at"] <= datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
                cursor.execute("""
                    DELETE FROM member_timeouts
                    WHERE server_id = ? AND user_id = ?
                """, (server_id, user_id))
                conn.commit()
                return None
            return dict(row)

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

    def toggle_message_reaction(self, message_id: int, user_name: str, emoji: str) -> bool:
        """Adds or removes a user's emoji reaction and returns whether it is active."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM message_reactions
                WHERE message_id = ? AND user_name = ? AND emoji = ?
            """, (message_id, user_name.strip(), emoji))
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM message_reactions WHERE id = ?", (row["id"],))
                active = False
            else:
                cursor.execute("""
                    INSERT INTO message_reactions (message_id, user_name, emoji, created_at)
                    VALUES (?, ?, ?, ?)
                """, (message_id, user_name.strip(), emoji, now_str))
                active = True
            conn.commit()
            return active

    def get_message_reactions(self, message_id: int) -> list:
        """Returns grouped reaction counts for a message."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emoji, COUNT(*) AS count
                FROM message_reactions
                WHERE message_id = ?
                GROUP BY emoji
                ORDER BY MIN(created_at) ASC
            """, (message_id,))
            return [dict(row) for row in cursor.fetchall()]

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
                        cursor.execute("SELECT id FROM users WHERE id = 1")
                        if cursor.fetchone():
                            cursor.execute("""
                                INSERT OR IGNORE INTO server_members (server_id, user_id, role, created_at)
                                VALUES (?, 1, 'owner', ?)
                            """, (s_id, now_str))
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

    def create_server_webhook(
        self,
        server_id: int,
        name: str,
        url: str,
        secret: str = "",
        events: str = "*"
    ) -> tuple:
        """Creates a server webhook configuration."""
        name = name.strip()
        url = url.strip()
        if not name:
            return False, "Nazwa webhooka nie może być pusta."
        if not url.startswith(("http://", "https://")):
            return False, "Niepoprawny adres URL webhooka."
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM servers WHERE id = ?", (server_id,))
            if not cursor.fetchone():
                return False, "Nie znaleziono serwera."
            cursor.execute("""
                INSERT INTO server_webhooks (
                    server_id, name, url, secret, events, is_active, created_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (server_id, name, url, secret, events.strip() or "*", now_str))
            conn.commit()
            return True, {
                "id": cursor.lastrowid,
                "server_id": server_id,
                "name": name,
                "url": url,
                "events": events.strip() or "*",
                "is_active": True
            }

    def get_server_webhooks(self, server_id: int) -> list:
        """Returns webhook configurations for a server."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, server_id, name, url, secret, events, is_active, created_at
                FROM server_webhooks
                WHERE server_id = ?
                ORDER BY id ASC
            """, (server_id,))
            result = []
            for row in cursor.fetchall():
                item = dict(row)
                item["is_active"] = bool(item["is_active"])
                result.append(item)
            return result

    def set_server_webhook_active(self, webhook_id: int, active: bool) -> bool:
        """Enables or disables a server webhook."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE server_webhooks
                SET is_active = ?
                WHERE id = ?
            """, (1 if active else 0, webhook_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_server_webhook(self, webhook_id: int) -> bool:
        """Deletes a server webhook and queued deliveries."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM server_webhooks WHERE id = ?", (webhook_id,))
            conn.commit()
            return cursor.rowcount > 0

    def dispatch_server_webhook(
        self,
        server_id: int,
        event_type: str,
        payload: Dict[str, Any]
    ) -> list:
        """Queues matching webhook deliveries with HMAC-SHA256 signatures."""
        event_type = event_type.strip()
        event_payload = json.dumps(
            {
                "event": event_type,
                "server_id": server_id,
                "payload": payload
            },
            ensure_ascii=False,
            sort_keys=True
        )
        queued = []
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, secret, events
                FROM server_webhooks
                WHERE server_id = ? AND is_active = 1
            """, (server_id,))
            webhooks = cursor.fetchall()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for webhook in webhooks:
                subscribed = webhook["events"].split(",")
                subscribed = [value.strip() for value in subscribed]
                if "*" not in subscribed and event_type not in subscribed:
                    continue
                signature = hmac.new(
                    webhook["secret"].encode("utf-8"),
                    event_payload.encode("utf-8"),
                    hashlib.sha256
                ).hexdigest()
                cursor.execute("""
                    INSERT INTO webhook_deliveries (
                        webhook_id, event_type, payload, signature, status, created_at
                    )
                    VALUES (?, ?, ?, ?, 'queued', ?)
                """, (
                    webhook["id"],
                    event_type,
                    event_payload,
                    signature,
                    now_str
                ))
                queued.append({
                    "webhook_id": webhook["id"],
                    "event_type": event_type,
                    "signature": signature,
                    "status": "queued"
                })
            conn.commit()
            return queued

    def get_webhook_deliveries(
        self,
        server_id: int,
        limit: int = 100
    ) -> list:
        """Returns recent queued webhook deliveries for a server."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.id, d.webhook_id, d.event_type, d.payload, d.signature,
                       d.status, d.created_at, w.name AS webhook_name
                FROM webhook_deliveries d
                JOIN server_webhooks w ON w.id = d.webhook_id
                WHERE w.server_id = ?
                ORDER BY d.id DESC
                LIMIT ?
            """, (server_id, max(1, int(limit))))
            return [dict(row) for row in cursor.fetchall()]

    def get_server_analytics(self, server_id: int) -> Dict[str, Any]:
        """Returns aggregate member, channel and message metrics for a server."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM servers WHERE id = ?", (server_id,))
            server = cursor.fetchone()
            if not server:
                return {
                    "server_id": server_id,
                    "server_name": "",
                    "member_count": 0,
                    "channel_count": 0,
                    "message_count": 0,
                    "role_counts": {},
                    "activity_count": 0
                }

            server_name = server["name"]
            cursor.execute("SELECT COUNT(*) FROM server_members WHERE server_id = ?", (server_id,))
            member_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM channels WHERE server_id = ?", (server_id,))
            channel_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE target LIKE ?
            """, (f"{server_name}#%",))
            message_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT role, COUNT(*) AS count
                FROM server_members
                WHERE server_id = ?
                GROUP BY role
            """, (server_id,))
            role_counts = {row["role"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("""
                SELECT COUNT(*) FROM member_activity_logs WHERE server_id = ?
            """, (server_id,))
            activity_count = cursor.fetchone()[0]

            return {
                "server_id": server_id,
                "server_name": server_name,
                "member_count": member_count,
                "channel_count": channel_count,
                "message_count": message_count,
                "role_counts": role_counts,
                "activity_count": activity_count
            }

    def set_server_member_role(
        self,
        server_id: int,
        user_id: int,
        role: str,
        actor_id: Optional[int] = None
    ) -> tuple:
        """Assigns owner, admin, moderator or member role to a server member."""
        role = role.strip().lower()
        if role not in ("owner", "admin", "moderator", "member"):
            return False, "Nieznana rola serwera."
        if role == "owner":
            return False, "Właściciela serwera można ustawić tylko podczas jego tworzenia."
        if actor_id is not None:
            actor_role = self.get_server_member_role(server_id, actor_id)
            if actor_role not in ("owner", "admin"):
                return False, "Brak uprawnień do zarządzania członkami."
            if user_id == actor_id and actor_role == "admin":
                return False, "Administrator nie może zmienić własnej roli."
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO server_members (server_id, user_id, role, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(server_id, user_id) DO UPDATE SET role = excluded.role
                """, (server_id, user_id, role, now_str))
                conn.commit()
                self.add_member_activity_log(
                    server_id,
                    actor_id,
                    "role_changed",
                    user_id,
                    f"Role changed to {role}"
                )
                return True, {"server_id": server_id, "user_id": user_id, "role": role}
        except Exception as exc:
            return False, f"Błąd bazy danych: {exc}"

    def get_server_member_role(self, server_id: int, user_id: int) -> str:
        """Returns a member role, defaulting to member."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role FROM server_members
                WHERE server_id = ? AND user_id = ?
            """, (server_id, user_id))
            row = cursor.fetchone()
            if row:
                return row["role"]
            cursor.execute("SELECT owner_id FROM servers WHERE id = ?", (server_id,))
            server = cursor.fetchone()
            if server and server["owner_id"] == user_id:
                return "owner"
            return "member"

    def get_server_members(self, server_id: int) -> list:
        """Returns server membership records."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sm.user_id, sm.role, sm.created_at, u.username, u.email
                FROM server_members sm
                JOIN users u ON u.id = sm.user_id
                WHERE sm.server_id = ?
                ORDER BY CASE sm.role
                    WHEN 'owner' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'moderator' THEN 3
                    ELSE 4
                END, u.username ASC
            """, (server_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_available_server_users(self, server_id: int) -> list:
        """Returns users that are not yet members of the server."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.username, u.email
                FROM users u
                WHERE u.id NOT IN (
                    SELECT user_id FROM server_members WHERE server_id = ?
                )
                ORDER BY u.username ASC
            """, (server_id,))
            return [dict(row) for row in cursor.fetchall()]

    def add_server_member(self, server_id: int, user_id: int, role: str = "member") -> tuple:
        """Adds a user to a server or updates their membership role."""
        role = role.strip().lower()
        if role not in ("admin", "moderator", "member"):
            return False, "Niepoprawna rola członka."
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                return False, "Nie znaleziono użytkownika."
            cursor.execute("SELECT id FROM servers WHERE id = ?", (server_id,))
            if not cursor.fetchone():
                return False, "Nie znaleziono serwera."
            cursor.execute("""
                INSERT INTO server_members (server_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(server_id, user_id) DO UPDATE SET role = excluded.role
            """, (server_id, user_id, role, now_str))
            conn.commit()
            self.add_member_activity_log(
                server_id,
                None,
                "member_added",
                user_id,
                f"Role set to {role}"
            )
            return True, {"server_id": server_id, "user_id": user_id, "role": role}

    def remove_server_member(self, server_id: int, user_id: int) -> tuple:
        """Removes a member while protecting the server owner."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT owner_id FROM servers WHERE id = ?", (server_id,))
            server = cursor.fetchone()
            if not server:
                return False, "Nie znaleziono serwera."
            if server["owner_id"] == user_id:
                return False, "Nie można usunąć właściciela serwera."
            cursor.execute("""
                DELETE FROM server_members
                WHERE server_id = ? AND user_id = ?
            """, (server_id, user_id))
            conn.commit()
            if cursor.rowcount == 0:
                return False, "Użytkownik nie jest członkiem serwera."
            self.add_member_activity_log(
                server_id,
                None,
                "member_removed",
                user_id,
                "Member removed"
            )
            return True, "Członek został usunięty."

    def can_manage_server(self, server_id: int, user_id: int) -> bool:
        """Owner and admin can manage server and channel structure."""
        return self.get_server_member_role(server_id, user_id) in ("owner", "admin")

    def can_moderate_server(self, server_id: int, user_id: int) -> bool:
        """Owner, admin and moderator can moderate messages."""
        return self.get_server_member_role(server_id, user_id) in ("owner", "admin", "moderator")

    def add_member_activity_log(
        self,
        server_id: int,
        actor_id: Optional[int],
        action: str,
        target_user_id: Optional[int] = None,
        details: str = ""
    ) -> int:
        """Writes a server-member moderation or role-change audit entry."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO member_activity_logs (
                    server_id, actor_id, target_user_id, action, details, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                server_id,
                actor_id,
                target_user_id,
                action.strip().lower(),
                details.strip(),
                now_str
            ))
            conn.commit()
            return cursor.lastrowid

    def get_member_activity_logs(
        self,
        server_id: int,
        limit: int = 200
    ) -> list:
        """Returns the newest member activity entries for a server."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    log.id,
                    log.server_id,
                    log.actor_id,
                    log.target_user_id,
                    log.action,
                    log.details,
                    log.created_at,
                    actor.username AS actor_name,
                    target.username AS target_name
                FROM member_activity_logs log
                LEFT JOIN users actor ON actor.id = log.actor_id
                LEFT JOIN users target ON target.id = log.target_user_id
                WHERE log.server_id = ?
                ORDER BY log.id DESC
                LIMIT ?
            """, (server_id, max(1, int(limit))))
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
                cursor.execute("SELECT id FROM users WHERE id = ?", (owner_id,))
                if cursor.fetchone():
                    cursor.execute("""
                        INSERT OR REPLACE INTO server_members (server_id, user_id, role, created_at)
                        VALUES (?, ?, 'owner', ?)
                    """, (server_id, owner_id, now_str))

                conn.commit()
                return True, {"id": server_id, "name": name, "icon": icon}
        except sqlite3.IntegrityError:
            return False, "Serwer o takiej nazwie już istnieje!"
        except Exception as e:
            return False, f"Błąd bazy danych: {e}"

    def delete_server(self, server_id: int, actor_id: Optional[int] = None) -> bool:
        """Usuwa serwer wraz ze wszystkimi kanałami (CASCADE)"""
        if actor_id is not None and not self.can_manage_server(server_id, actor_id):
            return False
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
                SELECT id, server_id, name, topic, channel_type, position, category_id
                FROM channels
                WHERE server_id = ?
                ORDER BY position ASC, id ASC
            """, (server_id,))
            return [dict(row) for row in cursor.fetchall()]

    def create_channel_category(
        self,
        server_id: int,
        name: str,
        position: int = 0
    ) -> tuple:
        """Creates a named channel category."""
        name = name.strip()
        if not name:
            return False, "Nazwa kategorii nie może być pusta."
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO channel_categories (
                        server_id, name, position, collapsed, created_at
                    )
                    VALUES (?, ?, ?, 0, ?)
                """, (server_id, name, max(0, int(position)), now_str))
                conn.commit()
                return True, {
                    "id": cursor.lastrowid,
                    "server_id": server_id,
                    "name": name,
                    "position": position,
                    "collapsed": False
                }
        except sqlite3.IntegrityError:
            return False, "Taka kategoria już istnieje na serwerze."

    def get_channel_categories(self, server_id: int) -> list:
        """Returns channel categories ordered by position."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, server_id, name, position, collapsed, created_at
                FROM channel_categories
                WHERE server_id = ?
                ORDER BY position ASC, name COLLATE NOCASE ASC
            """, (server_id,))
            result = []
            for row in cursor.fetchall():
                item = dict(row)
                item["collapsed"] = bool(item["collapsed"])
                result.append(item)
            return result

    def assign_channel_category(
        self,
        channel_id: int,
        category_id: Optional[int]
    ) -> bool:
        """Assigns or removes a channel category."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE channels
                SET category_id = ?
                WHERE id = ?
            """, (category_id, channel_id))
            conn.commit()
            return cursor.rowcount > 0

    def set_channel_category_collapsed(
        self,
        category_id: int,
        collapsed: bool
    ) -> bool:
        """Stores collapsed state for a channel category."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE channel_categories
                SET collapsed = ?
                WHERE id = ?
            """, (1 if collapsed else 0, category_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_grouped_channels(self, server_id: int) -> dict:
        """Groups channels under categories and uncategorized."""
        categories = self.get_channel_categories(server_id)
        channels = self.get_channels(server_id)
        grouped = {"uncategorized": []}
        for category in categories:
            grouped[str(category["id"])] = {
                "category": category,
                "channels": []
            }
        for channel in channels:
            category_id = channel.get("category_id")
            if category_id is not None and str(category_id) in grouped:
                grouped[str(category_id)]["channels"].append(channel)
            else:
                grouped["uncategorized"].append(channel)
        return grouped

    def search_and_sort_channels(
        self,
        server_id: int,
        query: str = "",
        sort_by: str = "position"
    ) -> list:
        """Filters and sorts channels by name/topic or configured position."""
        channels = self.get_channels(server_id)
        search_query = query.strip().lower()
        if search_query:
            channels = [
                channel for channel in channels
                if search_query in channel["name"].lower()
                or search_query in (channel.get("topic") or "").lower()
            ]

        sort_by = sort_by.strip().lower()
        if sort_by == "name":
            channels.sort(key=lambda channel: channel["name"].lower())
        elif sort_by == "name_desc":
            channels.sort(key=lambda channel: channel["name"].lower(), reverse=True)
        elif sort_by == "topic":
            channels.sort(key=lambda channel: (channel.get("topic") or "").lower())
        else:
            channels.sort(key=lambda channel: (channel.get("position", 0), channel["id"]))
        return channels

    def set_channel_permission(
        self,
        channel_id: int,
        role: str,
        permission: str,
        allowed: bool
    ) -> tuple:
        """Sets an allow or deny override for a role on a channel."""
        role = role.strip().lower()
        permission = permission.strip().lower()
        if role not in ("owner", "admin", "moderator", "member"):
            return False, "Nieznana rola kanału."
        if permission not in ("view", "send", "manage"):
            return False, "Nieznane uprawnienie kanału."
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM channels WHERE id = ?", (channel_id,))
            if not cursor.fetchone():
                return False, "Nie znaleziono kanału."
            cursor.execute("""
                INSERT INTO channel_permissions (channel_id, role, permission, allowed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel_id, role, permission)
                DO UPDATE SET allowed = excluded.allowed
            """, (channel_id, role, permission, 1 if allowed else 0))
            conn.commit()
            return True, {
                "channel_id": channel_id,
                "role": role,
                "permission": permission,
                "allowed": bool(allowed)
            }

    def get_channel_permissions(self, channel_id: int) -> list:
        """Returns all explicit permission overrides for a channel."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, permission, allowed
                FROM channel_permissions
                WHERE channel_id = ?
                ORDER BY role ASC, permission ASC
            """, (channel_id,))
            return [dict(row) for row in cursor.fetchall()]

    def can_access_channel(
        self,
        channel_id: int,
        server_role: str,
        permission: str = "view"
    ) -> bool:
        """Checks explicit channel overrides, then applies role inheritance."""
        server_role = server_role.strip().lower()
        permission = permission.strip().lower()
        if server_role not in ("owner", "admin", "moderator", "member"):
            return False
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT allowed FROM channel_permissions
                WHERE channel_id = ? AND role = ? AND permission = ?
            """, (channel_id, server_role, permission))
            override = cursor.fetchone()
            if override:
                return bool(override["allowed"])

        role_defaults = {
            "owner": {"view": True, "send": True, "manage": True},
            "admin": {"view": True, "send": True, "manage": True},
            "moderator": {"view": True, "send": True, "manage": False},
            "member": {"view": True, "send": True, "manage": False}
        }
        return role_defaults[server_role].get(permission, False)

    def get_accessible_channels(self, server_id: int, server_role: str) -> list:
        """Returns channels visible to a server role."""
        accessible = []
        for channel in self.get_channels(server_id):
            if self.can_access_channel(channel["id"], server_role, "view"):
                accessible.append(channel)
        return accessible

    def create_channel(
        self,
        server_id: int,
        name: str,
        topic: str = "",
        channel_type: str = "text",
        actor_id: Optional[int] = None
    ) -> tuple:
        """Tworzy nowy kanał w serwerze"""
        if actor_id is not None and not self.can_manage_server(server_id, actor_id):
            return False, "Brak uprawnień do tworzenia kanałów."
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
                return True, {
                    "id": channel_id,
                    "server_id": server_id,
                    "name": name,
                    "topic": topic,
                    "channel_type": channel_type
                }
        except sqlite3.IntegrityError:
            return False, "Taki kanał już istnieje na tym serwerze!"
        except Exception as e:
            return False, f"Błąd bazy danych: {e}"

    def join_voice_channel(
        self,
        channel_id: int,
        user_name: str,
        muted: bool = False,
        deafened: bool = False
    ) -> tuple:
        """Adds a mock voice participant to a voice channel."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_name = user_name.strip()
        if not user_name:
            return False, "Nazwa użytkownika jest wymagana."
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, channel_type FROM channels WHERE id = ?
            """, (channel_id,))
            channel = cursor.fetchone()
            if not channel:
                return False, "Nie znaleziono kanału."
            if channel["channel_type"] != "voice":
                return False, "Kanał nie jest kanałem głosowym."
            cursor.execute("""
                INSERT INTO voice_participants (
                    channel_id, user_name, muted, deafened, connected_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(channel_id, user_name) DO UPDATE SET
                    muted = excluded.muted,
                    deafened = excluded.deafened
            """, (
                channel_id,
                user_name,
                1 if muted else 0,
                1 if deafened else 0,
                now_str
            ))
            conn.commit()
            return True, {
                "channel_id": channel_id,
                "user_name": user_name,
                "muted": muted,
                "deafened": deafened
            }

    def leave_voice_channel(self, channel_id: int, user_name: str) -> bool:
        """Removes a mock voice participant from a channel."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM voice_participants
                WHERE channel_id = ? AND user_name = ?
            """, (channel_id, user_name.strip()))
            conn.commit()
            return cursor.rowcount > 0

    def get_voice_participants(self, channel_id: int) -> list:
        """Returns connected mock voice participants."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT channel_id, user_name, muted, deafened, connected_at
                FROM voice_participants
                WHERE channel_id = ?
                ORDER BY connected_at ASC, id ASC
            """, (channel_id,))
            result = []
            for row in cursor.fetchall():
                item = dict(row)
                item["muted"] = bool(item["muted"])
                item["deafened"] = bool(item["deafened"])
                result.append(item)
            return result

    def delete_channel(self, channel_id: int, actor_id: Optional[int] = None) -> bool:
        """Usuwa kanał z bazy danych"""
        if actor_id is not None:
            server_role = None
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT server_id FROM channels WHERE id = ?", (channel_id,))
                channel = cursor.fetchone()
                if channel:
                    cursor.execute("""
                        SELECT role FROM server_members
                        WHERE server_id = ? AND user_id = ?
                    """, (channel["server_id"], actor_id))
                    role_row = cursor.fetchone()
                    if role_row:
                        server_role = role_row["role"]
                    else:
                        cursor.execute("SELECT owner_id FROM servers WHERE id = ?", (channel["server_id"],))
                        server = cursor.fetchone()
                        if server and server["owner_id"] == actor_id:
                            server_role = "owner"
            if server_role not in ("owner", "admin"):
                return False
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
            conn.commit()
            return cursor.rowcount > 0
