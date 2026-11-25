"""
VOXEN MULTI-USER TYPING TRACKER
Śledzenie stanu pisania dla wielu użytkowników w czasie rzeczywistym z auto-decay i formatowaniem gramatycznym.
"""

import threading
import time
from typing import Dict, List, Optional


class TypingTracker:
    """Zarządza stanem pisania wielu użytkowników na kanałach i w wiadomościach prywatnych"""

    def __init__(self, default_expiry: float = 4.5):
        self.default_expiry = default_expiry
        self._lock = threading.Lock()
        # Struktura: { conversation_key: { username: last_active_timestamp } }
        self._typing_map: Dict[str, Dict[str, float]] = {}

    def user_started_typing(self, conversation: str, user: str) -> bool:
        """
        Rejestruje rozpoczęcie pisania przez użytkownika w danej konwersacji/kanale.
        Zwraca True, jeśli użytkownik został dodany lub jego timestamp odświeżony.
        """
        conv_key = conversation.strip()
        user_name = user.strip()
        if not conv_key or not user_name:
            return False

        with self._lock:
            if conv_key not in self._typing_map:
                self._typing_map[conv_key] = {}
            self._typing_map[conv_key][user_name] = time.time()
            return True

    def user_stopped_typing(self, conversation: str, user: str) -> bool:
        """
        Rejestruje zakończenie pisania przez użytkownika.
        Zwraca True jeśli użytkownik był w trakcie pisania i został usunięty.
        """
        conv_key = conversation.strip()
        user_name = user.strip()
        if not conv_key or not user_name:
            return False

        with self._lock:
            if conv_key in self._typing_map:
                if user_name in self._typing_map[conv_key]:
                    del self._typing_map[conv_key][user_name]
                    if not self._typing_map[conv_key]:
                        del self._typing_map[conv_key]
                    return True
            return False

    def clean_expired(self, expiry_seconds: Optional[float] = None) -> bool:
        """
        Usuwa użytkowników, których wskaźnik pisania wygasł (auto-decay).
        Zwraca True jeśli jakikolwiek użytkownik został usunięty.
        """
        expiry = expiry_seconds if expiry_seconds is not None else self.default_expiry
        now = time.time()
        changed = False

        with self._lock:
            empty_convs = []
            for conv, users in list(self._typing_map.items()):
                expired_users = [u for u, t in users.items() if now - t > expiry]
                for u in expired_users:
                    del users[u]
                    changed = True
                if not users:
                    empty_convs.append(conv)

            for conv in empty_convs:
                del self._typing_map[conv]

        return changed

    def get_typing_users(self, conversation: str, expiry_seconds: Optional[float] = None) -> List[str]:
        """Zwraca listę aktualnie piszących użytkowników w danej konwersacji"""
        conv_key = conversation.strip()
        expiry = expiry_seconds if expiry_seconds is not None else self.default_expiry
        now = time.time()

        with self._lock:
            if conv_key not in self._typing_map:
                return []
            active = [u for u, t in self._typing_map[conv_key].items() if now - t <= expiry]
            return sorted(active)

    def format_typing_text(self, conversation: str, expiry_seconds: Optional[float] = None) -> str:
        """
        Formatuje czytelny tekst wskaźnika pisania w języku polskim dla 1, 2, 3 lub więcej osób.
        Przykłady:
        - 0: ""
        - 1: "💬 Wincekk pisze..."
        - 2: "💬 Wincekk i Maxi3049 piszą..."
        - 3: "💬 Wincekk, Maxi3049 i Nemeczek piszą..."
        - 4+: "💬 Wincekk, Maxi3049 i 2 innych pisze..."
        """
        users = self.get_typing_users(conversation, expiry_seconds)
        count = len(users)

        if count == 0:
            return ""
        elif count == 1:
            return f"💬 {users[0]} pisze..."
        elif count == 2:
            return f"💬 {users[0]} i {users[1]} piszą..."
        elif count == 3:
            return f"💬 {users[0]}, {users[1]} i {users[2]} piszą..."
        else:
            others = count - 2
            others_word = "innych" if others > 1 else "inny"
            return f"💬 {users[0]}, {users[1]} i {others} {others_word} pisze..."

    def clear_conversation(self, conversation: str) -> None:
        """Czyści listę piszących dla wybranej konwersacji"""
        conv_key = conversation.strip()
        with self._lock:
            self._typing_map.pop(conv_key, None)

    def clear_all(self) -> None:
        """Czyści stan wszystkich konwersacji"""
        with self._lock:
            self._typing_map.clear()
