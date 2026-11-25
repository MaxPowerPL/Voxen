"""
VOXEN ASYNC DEVELOPMENT / MOCK SERVER (RFC 6455)
Lokalny serwer deweloperski WebSocket oparty wyłącznie o standardową bibliotekę Python.
Pozwala na testowanie komunikacji w czasie rzeczywistym bez potrzeby uruchamiania
zewnętrznych serwisów backendowych.
"""

import asyncio
import base64
import hashlib
import json
import logging
import struct
from typing import Dict, Set

from network.protocol import Packet, PacketFactory, PacketType
from network.websocket_client import OP_CLOSE, OP_PING, OP_PONG, OP_TEXT, WS_GUID

logger = logging.getLogger("Voxen.MockServer")


class MockWebSocketServer:
    """Lokalny serwer deweloperski WebSocket RFC 6455"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.clients: Set[asyncio.StreamWriter] = set()
        self.user_sessions: Dict[asyncio.StreamWriter, str] = {}
        self._running = False

    async def start(self) -> None:
        """Start serwera asynchronicznego"""
        self._running = True
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        logger.info(f"Mock Server uruchomiony na ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Zatrzymanie serwera"""
        self._running = False
        for client in list(self.clients):
            try:
                client.close()
                await client.wait_closed()
            except Exception:
                pass
        self.clients.clear()
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Obsługa pojedynczego połączenia klienta"""
        try:
            # 1. Odczyt żądania HTTP Handshake
            request_data = b""
            while b"\r\n\r\n" not in request_data:
                chunk = await reader.read(1024)
                if not chunk:
                    return
                request_data += chunk

            # Wyciągnięcie Sec-WebSocket-Key
            lines = request_data.decode("latin-1", errors="ignore").split("\r\n")
            sec_key = None
            for line in lines:
                if line.lower().startswith("sec-websocket-key:"):
                    sec_key = line.split(":", 1)[1].strip()
                    break

            if not sec_key:
                writer.close()
                return

            # Generowanie Sec-WebSocket-Accept
            accept_token = base64.b64encode(
                hashlib.sha1((sec_key + WS_GUID).encode("ascii")).digest()
            ).decode("ascii")

            handshake_resp = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_token}\r\n\r\n"
            )
            writer.write(handshake_resp.encode("latin-1"))
            await writer.drain()

            self.clients.add(writer)
            self.user_sessions[writer] = "Guest"

            # 2. Pętla ramek
            while self._running:
                header = await reader.readexactly(2)
                b1, b2 = header[0], header[1]

                opcode = b1 & 0x0F
                has_mask = (b2 & 0x80) != 0
                payload_len = b2 & 0x7F

                if payload_len == 126:
                    ext = await reader.readexactly(2)
                    payload_len = struct.unpack("!H", ext)[0]
                elif payload_len == 127:
                    ext = await reader.readexactly(8)
                    payload_len = struct.unpack("!Q", ext)[0]

                mask_key = await reader.readexactly(4) if has_mask else b""
                raw_payload = await reader.readexactly(payload_len)

                # Odmaskowanie
                if has_mask:
                    unmasked = bytearray(raw_payload)
                    for i in range(len(unmasked)):
                        unmasked[i] ^= mask_key[i % 4]
                    payload = bytes(unmasked)
                else:
                    payload = raw_payload

                if opcode == OP_TEXT:
                    await self._process_text_packet(writer, payload.decode("utf-8"))
                elif opcode == OP_PING:
                    await self._send_frame(writer, OP_PONG, payload)
                elif opcode == OP_CLOSE:
                    break

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception as e:
            logger.error(f"Błąd klienta w mock serwerze: {e}")
        finally:
            self.clients.discard(writer)
            self.user_sessions.pop(writer, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_text_packet(self, sender_writer: asyncio.StreamWriter, text: str) -> None:
        """Przetwarzanie pakietu protokołu Voxen i generowanie odpowiedzi / symulacji"""
        try:
            packet = Packet.from_json(text)
        except Exception:
            return

        # 1. Autentykacja
        if packet.type == PacketType.AUTH_REQUEST:
            auth_key = packet.payload.get("auth_key", "User")
            self.user_sessions[sender_writer] = auth_key
            resp = Packet(
                type=PacketType.AUTH_RESPONSE,
                payload={
                    "success": True,
                    "user": auth_key,
                    "message": "Pomyślnie uwierzytelniono w sieci Voxen."
                }
            )
            await self._send_packet(sender_writer, resp)

        # 2. Ping-Pong
        elif packet.type == PacketType.HEARTBEAT_PING:
            pong = PacketFactory.pong()
            await self._send_packet(sender_writer, pong)

        # 3. Pakiety pisania (Typing Indicator)
        elif packet.type in [PacketType.TYPING_START, PacketType.TYPING_STOP]:
            for client in list(self.clients):
                if client != sender_writer:
                    await self._send_packet(client, packet)

        # 4. Aktualizacja statusu i obecności (Presence)
        elif packet.type in [PacketType.STATUS_UPDATE, PacketType.PRESENCE_CHANGE]:
            for client in list(self.clients):
                if client != sender_writer:
                    await self._send_packet(client, packet)

        # 4b. Emoji reactions
        elif packet.type == PacketType.REACTION_UPDATE:
            for client in list(self.clients):
                if client != sender_writer:
                    await self._send_packet(client, packet)

        # 4c. Moderation updates
        elif packet.type in [PacketType.MESSAGE_DELETE, PacketType.MEMBER_TIMEOUT]:
            for client in list(self.clients):
                if client != sender_writer:
                    await self._send_packet(client, packet)

        # 5. Wiadomość na czacie
        elif packet.type == PacketType.MESSAGE_SEND:
            sender = packet.payload.get("sender", "Anonim")
            target = packet.payload.get("target", "General")
            content = packet.payload.get("content", "")
            is_dm = packet.payload.get("is_dm", True)
            attachments = packet.payload.get("attachments", [])

            # Potwierdzenie ACK dla nadawcy
            ack = Packet(
                type=PacketType.MESSAGE_ACK,
                payload={"message_id": packet.id, "status": "delivered"}
            )
            await self._send_packet(sender_writer, ack)

            # Rozesłanie jako MESSAGE_RECV do wszystkich pozostałych podłączonych klientów
            recv_packet = Packet(
                type=PacketType.MESSAGE_RECV,
                payload={
                    "id": packet.id,
                    "sender": sender,
                    "target": target,
                    "content": content,
                    "timestamp": packet.timestamp,
                    "is_dm": is_dm,
                    "attachments": attachments
                }
            )
            for client in list(self.clients):
                if client != sender_writer:
                    await self._send_packet(client, recv_packet)

            # SYMULACJA BOTA: Jeśli użytkownik pisze do Unity Bot lub Wincekk, odpowiadamy automatycznie po 800ms!
            if target in ["Unity Bot", "Wincekk", "Nemeczek"]:
                asyncio.create_task(self._simulate_bot_reply(sender_writer, target, sender, content))

    async def _simulate_bot_reply(
        self,
        target_writer: asyncio.StreamWriter,
        bot_name: str,
        user: str,
        incoming_content: str
    ) -> None:
        """Symulacja odpowiedzi bota/znajomego w celach deweloperskich"""
        # Symulacja "typing..."
        typing_pkt = PacketFactory.typing(bot_name, user, True)
        await self._send_packet(target_writer, typing_pkt)

        await asyncio.sleep(1.0)

        # Wyłączenie "typing..."
        stop_typing = PacketFactory.typing(bot_name, user, False)
        await self._send_packet(target_writer, stop_typing)

        # Treść odpowiedzi
        if bot_name == "Unity Bot":
            reply_text = f"🤖 [System Voxen Engine]: Pakiet odebrany pomyślnie. Latencja stabilna. Echo: '{incoming_content}'"
        else:
            reply_text = f"Siema {user}! Odebrałem Twoją wiadomość przez nowy Network Engine: '{incoming_content}'"

        bot_msg = Packet(
            type=PacketType.MESSAGE_RECV,
            payload={
                "sender": bot_name,
                "target": user,
                "content": reply_text
            }
        )
        await self._send_packet(target_writer, bot_msg)

    async def _send_packet(self, writer: asyncio.StreamWriter, packet: Packet) -> None:
        """Wysyła obiekt Packet zakodowany w JSON"""
        raw_json = packet.to_json().encode("utf-8")
        await self._send_frame(writer, OP_TEXT, raw_json)

    async def _send_frame(self, writer: asyncio.StreamWriter, opcode: int, data: bytes) -> None:
        """Wysyła ramkę WebSocket z poziomu serwera (ramki serwer->klient NIE SĄ maskowane)"""
        length = len(data)
        header = bytearray()
        header.append(0x80 | (opcode & 0x0F))

        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))

        frame = bytes(header) + data
        writer.write(frame)
        await writer.drain()
