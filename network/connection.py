"""
VOXEN CONNECTION ENGINE
Maszyna stanów połączenia, konfiguracja oraz telemetria.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Optional


class ConnectionState(str, Enum):
    """Stany maszyny połączenia sieciowego"""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


@dataclass
class ConnectionConfig:
    """Konfiguracja parametrów połączenia"""
    host: str = "127.0.0.1"
    port: int = 8765
    path: str = "/ws"
    use_ssl: bool = False
    heartbeat_interval: float = 15.0     # Co ile sekund wysyłać ping
    heartbeat_timeout: float = 8.0       # Ile sekund czekać na pong przed uznaniem za rozłączony
    reconnect_base_delay: float = 1.0    # Początkowe opóźnienie w reconnect (backoff)
    reconnect_max_delay: float = 30.0    # Maksymalne opóźnienie w reconnect
    reconnect_factor: float = 1.8        # Mnożnik wykładniczy
    max_reconnect_attempts: int = 0      # 0 = nieskończone próby

    @property
    def ws_uri(self) -> str:
        protocol = "wss" if self.use_ssl else "ws"
        return f"{protocol}://{self.host}:{self.port}{self.path}"


@dataclass
class ConnectionMetrics:
    """Telemetria i diagnostyka łącza w czasie rzeczywistym"""
    state: ConnectionState = ConnectionState.DISCONNECTED
    latency_ms: float = 0.0
    packets_sent: int = 0
    packets_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    reconnect_count: int = 0
    last_ping_time: Optional[float] = None
    last_pong_time: Optional[float] = None
    connected_at: Optional[float] = None

    def record_sent(self, byte_count: int) -> None:
        self.packets_sent += 1
        self.bytes_sent += byte_count

    def record_received(self, byte_count: int) -> None:
        self.packets_received += 1
        self.bytes_received += byte_count

    def record_pong(self) -> None:
        now = time.time()
        self.last_pong_time = now
        if self.last_ping_time:
            self.latency_ms = round((now - self.last_ping_time) * 1000.0, 2)
