"""
VOXEN ASYNC WEBSOCKET CLIENT (RFC 6455)
W pełni natywna implementacja klienta WebSocket oparta wyłącznie na standardowej
bibliotece Python (asyncio, hashlib, base64, os, struct, ssl).
Brak konieczności instalowania zewnętrznych zależności C/pip.
"""

import asyncio
import base64
import hashlib
import os
import ssl
import struct
from typing import Optional, Tuple


# RFC 6455 GUID stała do walidacji handshake
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Opcodes
OP_CONT = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


class AsyncWebSocketClient:
    """Natywny asynchroniczny klient WebSocket RFC 6455"""

    def __init__(self, host: str, port: int, path: str = "/", use_ssl: bool = False):
        self.host = host
        self.port = port
        self.path = path if path.startswith("/") else f"/{path}"
        self.use_ssl = use_ssl

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected: bool = False
        self._close_sent: bool = False
        self._lock = asyncio.Lock()

    async def connect(self, timeout: float = 10.0) -> None:
        """Nawiązuje połączenie TCP i przeprowadza handshake WebSocket"""
        ssl_ctx = ssl.create_default_context() if self.use_ssl else None

        # Otwarcie strumienia TCP
        connect_coro = asyncio.open_connection(
            self.host, self.port, ssl=ssl_ctx
        )
        self.reader, self.writer = await asyncio.wait_for(connect_coro, timeout=timeout)

        # Generowanie klucza Sec-WebSocket-Key
        raw_nonce = os.urandom(16)
        sec_key = base64.b64encode(raw_nonce).decode("ascii")

        # Budowa żądania HTTP Upgrade
        handshake_req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"User-Agent: Voxen-Client/0.0.1-alpha\r\n\r\n"
        )

        self.writer.write(handshake_req.encode("latin-1"))
        await self.writer.drain()

        # Oczekiwanie na odpowiedź serwera (101 Switching Protocols)
        response_header = b""
        while b"\r\n\r\n" not in response_header:
            chunk = await asyncio.wait_for(self.reader.read(1024), timeout=timeout)
            if not chunk:
                raise ConnectionError("Połączenie przerwane podczas handshake WebSocket.")
            response_header += chunk

        status_line = response_header.split(b"\r\n")[0].decode("latin-1")
        if "101" not in status_line:
            raise ConnectionError(f"Nieudany handshake serwera WebSocket: {status_line}")

        # Walidacja Sec-WebSocket-Accept
        expected_accept = base64.b64encode(
            hashlib.sha1((sec_key + WS_GUID).encode("ascii")).digest()
        ).decode("ascii")

        header_text = response_header.decode("latin-1", errors="ignore").lower()
        if f"sec-websocket-accept: {expected_accept.lower()}" not in header_text:
            raise ConnectionError("Błędny token Sec-WebSocket-Accept od serwera.")

        self.is_connected = True
        self._close_sent = False

    async def send_text(self, text: str) -> int:
        """Wysyła ramkę tekstową (zamaskowaną zgodnie z wymogami RFC 6455 dla klienta)"""
        return await self._send_frame(OP_TEXT, text.encode("utf-8"))

    async def send_ping(self, payload: bytes = b"") -> int:
        """Wysyła ramkę Ping"""
        return await self._send_frame(OP_PING, payload)

    async def send_pong(self, payload: bytes = b"") -> int:
        """Wysyła ramkę Pong"""
        return await self._send_frame(OP_PONG, payload)

    async def _send_frame(self, opcode: int, data: bytes) -> int:
        """Konstruuje i wysyła zamaskowaną ramkę WebSocket"""
        if not self.is_connected or not self.writer:
            raise ConnectionResetError("Brak aktywnego połączenia WebSocket.")

        async with self._lock:
            length = len(data)
            header = bytearray()

            # FIN (1) + RSV1-3 (0) + Opcode
            header.append(0x80 | (opcode & 0x0F))

            # MASK = 1 (klient ZAWSZE maskuje dane)
            if length <= 125:
                header.append(0x80 | length)
            elif length <= 65535:
                header.append(0x80 | 126)
                header.extend(struct.pack("!H", length))
            else:
                header.append(0x80 | 127)
                header.extend(struct.pack("!Q", length))

            # 4-bajtowy klucz maskowania
            mask_key = os.urandom(4)
            header.extend(mask_key)

            # Zamaskowanie danych (XOR z mask_key)
            masked_data = bytearray(data)
            for i in range(len(masked_data)):
                masked_data[i] ^= mask_key[i % 4]

            frame = bytes(header) + bytes(masked_data)
            self.writer.write(frame)
            await self.writer.drain()
            return len(frame)

    async def receive_frame(self) -> Tuple[int, bytes]:
        """
        Odczytuje następną kompletną ramkę WebSocket ze strumienia.
        Zwraca: (opcode, odmaskowany_payload)
        """
        if not self.is_connected or not self.reader:
            raise ConnectionResetError("Brak aktywnego połączenia WebSocket.")

        # Odczyt 2 bajtów nagłówka
        header_bytes = await self.reader.readexactly(2)
        b1, b2 = header_bytes[0], header_bytes[1]

        fin = (b1 & 0x80) != 0
        opcode = b1 & 0x0F
        has_mask = (b2 & 0x80) != 0
        payload_len = b2 & 0x7F

        if payload_len == 126:
            ext_len = await self.reader.readexactly(2)
            payload_len = struct.unpack("!H", ext_len)[0]
        elif payload_len == 127:
            ext_len = await self.reader.readexactly(8)
            payload_len = struct.unpack("!Q", ext_len)[0]

        mask_key = b""
        if has_mask:
            mask_key = await self.reader.readexactly(4)

        payload = await self.reader.readexactly(payload_len)

        # Odmaskowanie jeśli serwer przesłał maskę (rzadkie, ale wymagane przez standard)
        if has_mask:
            unmasked = bytearray(payload)
            for i in range(len(unmasked)):
                unmasked[i] ^= mask_key[i % 4]
            payload = bytes(unmasked)

        return opcode, payload

    async def close(self, code: int = 1000) -> None:
        """Bezpieczne zamykanie połączenia (RFC 6455 Close handshake)"""
        if not self.is_connected:
            return

        self.is_connected = False
        try:
            if not self._close_sent and self.writer and not self.writer.is_closing():
                close_payload = struct.pack("!H", code)
                await self._send_frame(OP_CLOSE, close_payload)
                self._close_sent = True
        except Exception:
            pass
        finally:
            if self.writer:
                try:
                    self.writer.close()
                    await self.writer.wait_closed()
                except Exception:
                    pass
                self.writer = None
            self.reader = None
