"""
VOXEN SESSION MANAGER
Zarządzanie trwałymi tokenami sesji, wznawianiem logowania i bezpieczeństwem tokenów.
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import secrets
from typing import Optional


class SessionManager:
    """Zarządca tokenów sesji po stronie klienta"""

    DEFAULT_SESSION_FILE = ".voxen_session"
    DEFAULT_DURATION_DAYS = 30

    def __init__(self, session_file: Optional[str] = None):
        self.session_file = Path(session_file or self.DEFAULT_SESSION_FILE)

    @staticmethod
    def generate_token() -> str:
        """Generuje 48-bajtowy losowy token URL-safe (kryptograficznie bezpieczny)"""
        return secrets.token_urlsafe(48)

    def save_local_token(self, token: str, email: str) -> None:
        """Zapisuje aktywny token sesji w lokalnym pliku stanu"""
        try:
            data = {
                "token": token,
                "email": email,
                "created_at": datetime.now().isoformat()
            }
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Błąd zapisu tokenu sesji: {e}")

    def get_local_token(self) -> Optional[str]:
        """Odczytuje token sesji z lokalnego pliku jeśli istnieje"""
        if not self.session_file.exists():
            return None

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("token")
        except Exception:
            return None

    def clear_local_session(self) -> None:
        """Usuwa lokalny plik sesji (wylogowanie)"""
        try:
            if self.session_file.exists():
                self.session_file.unlink()
        except Exception as e:
            print(f"Błąd usuwania pliku sesji: {e}")
