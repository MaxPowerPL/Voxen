"""
VOXEN USER PRESENCE TRACKER
Zarządzanie stanem obecności użytkowników (Online, Idle, DND, Offline) w modelu MVC.
"""

import threading
from typing import Dict, Optional, Tuple
from utils import Colors


class PresenceTracker:
    """Śledzi statusy obecności użytkowników w czasie rzeczywistym"""

    STATUS_ONLINE = "online"
    STATUS_IDLE = "idle"
    STATUS_DND = "dnd"
    STATUS_OFFLINE = "offline"

    # Definicje wizualne dla statusów
    STATUS_CONFIG = {
        "online": {
            "name": "Dostępny",
            "dot": "🟢",
            "color": Colors.ONLINE,
            "description": "Widoczny jako dostępny dla wszystkich"
        },
        "idle": {
            "name": "Zaraz wracam",
            "dot": "🟡",
            "color": Colors.IDLE,
            "description": "Z dala od klawiatury"
        },
        "dnd": {
            "name": "Nie przeszkadzać",
            "dot": "🔴",
            "color": Colors.DND,
            "description": "Wycisza wszystkie powiadomienia i dźwięki"
        },
        "offline": {
            "name": "Niewidoczny",
            "dot": "⚪",
            "color": Colors.OFFLINE,
            "description": "Widoczny jako offline, ale z pełnym dostępem"
        }
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._presence_map: Dict[str, Dict[str, str]] = {}

    def set_user_presence(self, username: str, status: str, custom_status: str = "") -> bool:
        """
        Zapisuje lub aktualizuje status użytkownika.
        Zwraca True jeśli status uległ zmianie.
        """
        user_key = username.strip().lower()
        status_clean = status.lower().strip()
        if status_clean not in self.STATUS_CONFIG:
            status_clean = self.STATUS_ONLINE

        with self._lock:
            prev = self._presence_map.get(user_key)
            new_data = {
                "status": status_clean,
                "custom_status": custom_status.strip()
            }
            if prev == new_data:
                return False
            self._presence_map[user_key] = new_data
            return True

    def get_user_presence(self, username: str) -> Dict[str, str]:
        """Zwraca słownik z obecnością użytkownika"""
        user_key = username.strip().lower()
        with self._lock:
            data = self._presence_map.get(user_key)
            if data:
                return dict(data)
            return {"status": self.STATUS_ONLINE, "custom_status": ""}

    @classmethod
    def get_status_info(cls, status: str) -> Tuple[str, str, str]:
        """
        Zwraca krotkę (kolor_hex, nazwa_polska, emoji_kropka) dla podanego statusu.
        """
        clean = status.lower().strip()
        info = cls.STATUS_CONFIG.get(clean, cls.STATUS_CONFIG["online"])
        return info["color"], info["name"], info["dot"]
