"""
VOXEN NETWORK PROTOCOL
Definicje pakietów, typów zdarzeń i serializacja komunikatów real-time.
"""

from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, Optional
import json
import time
import uuid


class PacketType(str, Enum):
    """Typy pakietów protokołu Voxen"""
    # Autentykacja i sesja
    HANDSHAKE = "handshake"
    AUTH_REQUEST = "auth_request"
    AUTH_RESPONSE = "auth_response"
    HEARTBEAT_PING = "heartbeat_ping"
    HEARTBEAT_PONG = "heartbeat_pong"
    DISCONNECT = "disconnect"

    # Wiadomości
    MESSAGE_SEND = "message_send"
    MESSAGE_RECV = "message_recv"
    MESSAGE_ACK = "message_ack"

    # Status i obecność
    STATUS_UPDATE = "status_update"
    PRESENCE_CHANGE = "presence_change"
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"

    # Kanały i serwery
    CHANNEL_JOIN = "channel_join"
    CHANNEL_LEAVE = "channel_leave"
    SERVER_SYNC = "server_sync"

    # Błędy systemowe
    SYSTEM_ERROR = "system_error"


@dataclass
class Packet:
    """
    Bazowy pakiet sieciowy protokołu Voxen.
    Zapewnia jednoznaczny identyfikator, znacznik czasu i typowany ładunek (payload).
    """
    type: PacketType
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serializacja pakietu do formatu JSON"""
        data = {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, PacketType) else self.type,
            "timestamp": self.timestamp,
            "payload": self.payload
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw_data: str) -> "Packet":
        """Deserializacja surowego JSON do obiektu Packet"""
        parsed = json.loads(raw_data)
        return cls(
            type=PacketType(parsed["type"]),
            payload=parsed.get("payload", {}),
            id=parsed.get("id", str(uuid.uuid4())),
            timestamp=parsed.get("timestamp", time.time())
        )


# Helpery fabryczne do tworzenia typowych pakietów
class PacketFactory:
    """Fabryka pakietów ułatwiająca tworzenie typowych wiadomości"""

    @staticmethod
    def auth(token_or_email: str, client_version: str = "0.0.1-alpha") -> Packet:
        return Packet(
            type=PacketType.AUTH_REQUEST,
            payload={
                "auth_key": token_or_email,
                "version": client_version,
                "os": "Windows"
            }
        )

    @staticmethod
    def ping() -> Packet:
        return Packet(type=PacketType.HEARTBEAT_PING)

    @staticmethod
    def pong() -> Packet:
        return Packet(type=PacketType.HEARTBEAT_PONG)

    @staticmethod
    def chat_message(
        sender: str,
        recipient_or_channel: str,
        content: str,
        is_dm: bool = True,
        attachments: Optional[list] = None
    ) -> Packet:
        return Packet(
            type=PacketType.MESSAGE_SEND,
            payload={
                "sender": sender,
                "target": recipient_or_channel,
                "content": content,
                "is_dm": is_dm,
                "attachments": attachments or []
            }
        )

    @staticmethod
    def status_update(user: str, status: str, custom_status: str = "") -> Packet:
        return Packet(
            type=PacketType.STATUS_UPDATE,
            payload={
                "user": user,
                "status": status,  # online, idle, dnd, offline
                "custom_status": custom_status
            }
        )

    @staticmethod
    def typing(user: str, target: str, is_typing: bool) -> Packet:
        pkt_type = PacketType.TYPING_START if is_typing else PacketType.TYPING_STOP
        return Packet(
            type=pkt_type,
            payload={
                "user": user,
                "target": target
            }
        )
