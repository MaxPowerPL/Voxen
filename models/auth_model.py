"""
MODEL - Zarządzanie danymi użytkowników, bezpieczeństwem i sesjami (SQLite + scrypt)
"""

from typing import Any, Dict, Optional, Tuple
from database.db import DatabaseManager
from security.crypto import PasswordHasher
from security.session import SessionManager


class AuthModel:
    """Model zarządzający autentykacją i bezpieczeństwem kont (Model w MVC)"""

    def __init__(self, db_path: str = "voxen.db"):
        """
        Inicjalizacja modelu opartego na SQLite i scrypt

        Args:
            db_path: Ścieżka do pliku bazy SQLite
        """
        self.db = DatabaseManager(db_path)
        self.session_manager = SessionManager()

    def validate_credentials(self, email: str, password: str) -> Tuple[bool, str | Dict[str, Any]]:
        """
        Sprawdza poprawność danych logowania i tworzy trwałą sesję przy sukcesie.

        Args:
            email: Email użytkownika
            password: Hasło użytkownika

        Returns:
            tuple: (sukces, dane_użytkownika lub komunikat_błędu)
        """
        email = email.strip() if email else ""

        if not email or not password:
            return False, "Wypełnij wszystkie pola!"

        if "@" not in email:
            return False, "Podaj poprawny adres email!"

        user = self.db.get_user_by_email(email)
        if not user:
            return False, "Użytkownik nie istnieje!"

        # Weryfikacja hasła z wykorzystaniem stałoczasowego scrypt
        is_valid = PasswordHasher.verify_password(password, user["password_hash"])
        if not is_valid:
            return False, "Nieprawidłowe hasło!"

        # Utwórz token sesji i zapisz lokalnie
        token = self.db.create_session(user["id"])
        self.session_manager.save_local_token(token, user["email"])

        # Zwracamy bezpieczny słownik bez hasha hasła
        user_data = {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "security": user["security"],
            "last_login": user["last_login"]
        }
        return True, user_data

    def check_saved_session(self) -> Optional[Dict[str, Any]]:
        """
        Sprawdza czy na dysku istnieje aktywna, niewygasła sesja (Auto-Login).

        Returns:
            dict z danymi użytkownika lub None
        """
        token = self.session_manager.get_local_token()
        if not token:
            return None

        user = self.db.validate_session(token)
        if user:
            self.db.update_last_login(user["email"])
        return user

    def logout(self) -> None:
        """Wylogowuje użytkownika, unieważnia token w bazie i usuwa plik sesji"""
        token = self.session_manager.get_local_token()
        if token:
            self.db.revoke_session(token)
        self.session_manager.clear_local_session()

    def register_user(
        self,
        email: str,
        password: str,
        username: Optional[str] = None
    ) -> Tuple[bool, str | Dict[str, Any]]:
        """Rejestruje nowego użytkownika w bazie SQLite"""
        return self.db.create_user(email, password, username=username)

    def update_last_login(self, email: str) -> None:
        """Aktualizuje datę ostatniego logowania w bazie SQLite"""
        self.db.update_last_login(email)

    def get_user_info(self, email: str) -> Optional[Dict[str, Any]]:
        """Pobiera informacje o użytkowniku"""
        user = self.db.get_user_by_email(email)
        if user:
            return {
                "id": user["id"],
                "email": user["email"],
                "username": user["username"],
                "security": user["security"],
                "last_login": user["last_login"]
            }
        return None
