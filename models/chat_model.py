"""
MODEL - Zarządzanie historią wiadomości czatu w SQLite (Warstwa Modelu w MVC)
"""

from typing import Any, Dict, List, Optional
from database.db import DatabaseManager


class ChatModel:
    """Model zarządzający trwałą historią wiadomości w bazie SQLite"""

    def __init__(self, db: Optional[DatabaseManager] = None, db_path: str = "voxen.db"):
        self.db = db or DatabaseManager(db_path=db_path)

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
        """Zapisuje wiadomość (przychodzącą lub wychodzącą) w bazie danych"""
        return self.db.save_message(
            sender=sender,
            target=target,
            content=content,
            packet_id=packet_id,
            timestamp=timestamp,
            is_dm=is_dm,
            is_read=is_read
        )

    def mark_as_read(self, conversation: str, current_user: str) -> int:
        """Oznacza wiadomości w danej konwersacji lub kanale jako przeczytane"""
        return self.db.mark_as_read(conversation=conversation, current_user=current_user)

    def get_unread_count(self, conversation: str, current_user: str) -> int:
        """Zwraca liczbę nieprzeczytanych wiadomości dla danej konwersacji"""
        return self.db.get_unread_count(conversation=conversation, current_user=current_user)

    def get_all_unread_counts(self, current_user: str) -> Dict[str, int]:
        """Zwraca mapę nieprzeczytanych wiadomości dla użytkownika"""
        return self.db.get_all_unread_counts(current_user=current_user)

    def get_history(
        self,
        conversation: str,
        current_user: str,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Pobiera sformatowaną historię wiadomości dla wybranej konwersacji"""
        return self.db.get_conversation_history(
            conversation=conversation,
            current_user=current_user,
            limit=limit
        )

    def search_history(
        self,
        conversation: str,
        current_user: str,
        query: str = "",
        sender: str = "",
        timestamp: str = "",
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Searches messages in the selected DM or channel."""
        return self.db.search_messages(
            conversation=conversation,
            current_user=current_user,
            query=query,
            sender=sender,
            timestamp=timestamp,
            limit=limit
        )

    def search_messages(
        self,
        conversation: str,
        current_user: str,
        query: str = "",
        sender: str = "",
        timestamp: str = "",
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Alias for search_history."""
        return self.search_history(
            conversation=conversation,
            current_user=current_user,
            query=query,
            sender=sender,
            timestamp=timestamp,
            limit=limit
        )

    def clear_history(self, conversation: str, current_user: str) -> None:
        """Usuwa historię wiadomości danej konwersacji z bazy danych"""
        self.db.clear_conversation_history(
            conversation=conversation,
            current_user=current_user
        )

    def delete_message(self, message_id: int) -> bool:
        """Deletes a message through the database layer."""
        return self.db.delete_message(message_id)
