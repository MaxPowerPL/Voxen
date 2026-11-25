"""
MODEL - Zarządzanie serwerami i kanałami tekstowymi w SQLite (Warstwa Modelu w MVC)
"""

from datetime import datetime, timedelta
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
        channel_type: str = "text",
        actor_id: Optional[int] = None
    ) -> Tuple[bool, Dict[str, Any] | str]:
        """Tworzy nowy kanał tekstowy na serwerze"""
        return self.db.create_channel(
            server_id=server_id,
            name=name,
            topic=topic,
            channel_type=channel_type,
            actor_id=actor_id
        )

    def delete_channel(self, channel_id: int, actor_id: Optional[int] = None) -> bool:
        """Usuwa kanał z serwera"""
        return self.db.delete_channel(channel_id=channel_id, actor_id=actor_id)

    def set_member_role(
        self,
        server_id: int,
        user_id: int,
        role: str,
        actor_id: Optional[int] = None
    ) -> tuple:
        """Assigns a role in a server."""
        return self.db.set_server_member_role(server_id, user_id, role, actor_id)

    def get_member_role(self, server_id: int, user_id: int) -> str:
        """Gets a member role in a server."""
        return self.db.get_server_member_role(server_id, user_id)

    def get_members(self, server_id: int) -> list:
        """Gets server membership records."""
        return self.db.get_server_members(server_id)

    def can_manage(self, server_id: int, user_id: int) -> bool:
        """Checks owner/admin channel-management permission."""
        return self.db.can_manage_server(server_id, user_id)

    def can_moderate(self, server_id: int, user_id: int) -> bool:
        """Checks owner/admin/moderator message-moderation permission."""
        return self.db.can_moderate_server(server_id, user_id)

    def get_available_users(self, server_id: int) -> list:
        """Gets users that can be added to a server."""
        return self.db.get_available_server_users(server_id)

    def add_member(self, server_id: int, user_id: int, role: str = "member") -> tuple:
        """Adds or updates a server member."""
        return self.db.add_server_member(server_id, user_id, role)

    def remove_member(self, server_id: int, user_id: int) -> tuple:
        """Removes a server member."""
        return self.db.remove_server_member(server_id, user_id)

    def timeout_member(self, server_id: int, user_id: int, minutes: int) -> tuple:
        """Times out a member for a bounded number of minutes."""
        minutes = max(1, min(int(minutes), 10080))
        expires = datetime.now() + timedelta(minutes=minutes)
        expires_at = expires.strftime("%Y-%m-%d %H:%M:%S")
        if not self.db.timeout_server_member(server_id, user_id, expires_at):
            return False, "Nie udało się zapisać timeoutu."
        return True, expires_at

    def get_member_timeout(self, server_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Gets active timeout metadata for a member."""
        return self.db.get_member_timeout(server_id, user_id)

    def log_activity(
        self,
        server_id: int,
        actor_id: Optional[int],
        action: str,
        target_user_id: Optional[int] = None,
        details: str = ""
    ) -> int:
        """Writes an activity log entry."""
        return self.db.add_member_activity_log(
            server_id,
            actor_id,
            action,
            target_user_id,
            details
        )

    def get_activity_logs(self, server_id: int, limit: int = 200) -> list:
        """Gets server member activity logs."""
        return self.db.get_member_activity_logs(server_id, limit)

    def get_analytics(self, server_id: int) -> Dict[str, Any]:
        """Gets aggregate server analytics."""
        return self.db.get_server_analytics(server_id)

    def set_channel_permission(
        self,
        channel_id: int,
        role: str,
        permission: str,
        allowed: bool
    ) -> tuple:
        """Sets a channel permission override."""
        return self.db.set_channel_permission(channel_id, role, permission, allowed)

    def get_channel_permissions(self, channel_id: int) -> list:
        """Gets channel permission overrides."""
        return self.db.get_channel_permissions(channel_id)

    def can_access_channel(
        self,
        channel_id: int,
        server_role: str,
        permission: str = "view"
    ) -> bool:
        """Checks channel access or action permission."""
        return self.db.can_access_channel(channel_id, server_role, permission)

    def get_accessible_channels(self, server_id: int, server_role: str) -> list:
        """Gets channels visible to a server role."""
        return self.db.get_accessible_channels(server_id, server_role)
