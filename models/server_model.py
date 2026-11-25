"""
MODEL - Zarządzanie serwerami i kanałami tekstowymi w SQLite (Warstwa Modelu w MVC)
"""

from typing import Any, Dict, List, Optional, Tuple
from database.db import DatabaseManager


class ServerModel:
    """Model zarządzający serwerami i kanałami w bazie danych SQLite"""

    def __init__(self, db: Optional[DatabaseManager] = None, db_path: str = "voxen.db"):
        self.db = db or DatabaseManager(db_path=db_path)

    def get_all_servers(self) -> List[Dict[str, Any]]:
        """Zwraca listę wszystkich dostępnych serwerów"""
        return self.db.get_servers()

    def create_server(
        self,
        name: str,
        icon: str = "📁",
        owner_id: int = 1
    ) -> Tuple[bool, Dict[str, Any] | str]:
        """Tworzy nowy serwer wraz z domyślnym kanałem"""
        return self.db.create_server(name=name, icon=icon, owner_id=owner_id)

    def delete_server(self, server_id: int) -> bool:
        """Usuwa serwer i wszystkie jego kanały"""
        return self.db.delete_server(server_id=server_id)

    def get_channels(self, server_id: int) -> List[Dict[str, Any]]:
        """Zwraca listę kanałów dla wskazanego serwera"""
        return self.db.get_channels(server_id=server_id)

    def create_channel(
        self,
        server_id: int,
        name: str,
        topic: str = "",
        channel_type: str = "text"
    ) -> Tuple[bool, Dict[str, Any] | str]:
        """Tworzy nowy kanał tekstowy na serwerze"""
        return self.db.create_channel(
            server_id=server_id,
            name=name,
            topic=topic,
            channel_type=channel_type
        )

    def delete_channel(self, channel_id: int) -> bool:
        """Usuwa kanał z serwera"""
        return self.db.delete_channel(channel_id=channel_id)
