"""
VOXEN NETWORK ENGINE (CLIENT)
Wielowątkowy, asynchroniczny silnik sieciowy czasu rzeczywistego.
Obsługuje:
- Dedykowany wątek roboczy (asyncio event loop) oddzielony od głównego wątku UI.
- Automatyczną rekonwersję z backoffem wykładniczym.
- Pętlę Heartbeat (Ping/Pong Watchdog) z pomiarem latencji.
- Wzorzec Observer / Event Dispatcher z bezpiecznym przekazywaniem zdarzeń do pętli Tkinter.
"""

import asyncio
import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from network.connection import ConnectionConfig, ConnectionMetrics, ConnectionState
from network.protocol import Packet, PacketFactory, PacketType
from network.websocket_client import AsyncWebSocketClient, OP_CLOSE, OP_PING, OP_PONG, OP_TEXT

logger = logging.getLogger("Voxen.Network")


class NetworkClient:
    """Główny silnik sieciowy Voxen"""

    def __init__(
        self,
        config: Optional[ConnectionConfig] = None,
        ui_dispatcher: Optional[Callable[[Callable, Any], None]] = None
    ):
        """
        Inicjalizacja silnika sieciowego.

        Args:
            config: Konfiguracja połączenia (domyślnie 127.0.0.1:8765)
            ui_dispatcher: Funkcja delegująca wykonanie do wątku UI (np. app.after(0, func, arg))
        """
        self.config = config or ConnectionConfig()
        self.metrics = ConnectionMetrics()
        self.ui_dispatcher = ui_dispatcher

        # Stan wątkowy
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._ws_client: Optional[AsyncWebSocketClient] = None

        # Kolejki i synchronizacja
        self._send_queue: Optional[asyncio.Queue] = None
        self._state_lock = threading.Lock()

        # Rejestr listenerów zdarzeń: {PacketType: [callable, ...]}
        self._listeners: Dict[str, List[Callable[[Packet], None]]] = {}
        self._state_listeners: List[Callable[[ConnectionState], None]] = []

        # Token / Email do ponownej autentykacji po reconnect
        self._cached_auth_key: Optional[str] = None

    # ==========================================
    # API ZARZĄDZANIA CYKLEM ŻYCIA (THREADING)
    # ==========================================

    def start(self) -> None:
        """Uruchamia silnik sieciowy w osobnym wątku roboczym"""
        with self._state_lock:
            if self._running:
                return
            self._running = True

        self._thread = threading.Thread(
            target=self._run_event_loop,
            name="Voxen-Network-Worker",
            daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Bezpiecznie zatrzymuje silnik i wątek roboczy"""
        with self._state_lock:
            if not self._running:
                return
            self._running = False

        if self._loop and self._loop.is_running():
            async def _cleanup():
                # Anulowanie wszystkich pozostałych zadań w pętli
                tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if self._ws_client:
                    await self._ws_client.close()
                self._loop.stop()

            try:
                future = asyncio.run_coroutine_threadsafe(_cleanup(), self._loop)
                future.result(timeout=2.0)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._set_state(ConnectionState.CLOSED)

    def _run_event_loop(self) -> None:
        """Punkt wejścia dedykowanego wątku sieciowego"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._send_queue = asyncio.Queue()

        try:
            self._loop.run_until_complete(self._main_network_task())
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except Exception as e:
            logger.error(f"Nieoczekiwany wyjątek w pętli sieciowej: {e}")
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.close()

    # ==========================================
    # GŁÓWNA PĘTLA ASYNCHRONICZNA & RECONNECT
    # ==========================================

    async def _main_network_task(self) -> None:
        """Nadrzędna pętla zarządzająca połączeniem i automatyczną rekonwersją"""
        attempt = 0

        while self._running:
            try:
                self._set_state(
                    ConnectionState.CONNECTING if attempt == 0 else ConnectionState.RECONNECTING
                )

                self._ws_client = AsyncWebSocketClient(
                    host=self.config.host,
                    port=self.config.port,
                    path=self.config.path,
                    use_ssl=self.config.use_ssl
                )

                await self._ws_client.connect(timeout=5.0)

                # Połączenie udane
                attempt = 0
                self.metrics.connected_at = time.time()
                self._set_state(ConnectionState.CONNECTED)

                # Auto-autentykacja po reconnect jeśli klucz jest znany
                if self._cached_auth_key:
                    await self._send_packet_internal(
                        PacketFactory.auth(self._cached_auth_key)
                    )

                # Uruchomienie równoległych zadań: odbiór, wysyłka, heartbeat
                recv_task = asyncio.create_task(self._receive_loop())
                send_task = asyncio.create_task(self._send_loop())
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                # Czekamy aż którekolwiek zadanie rzuci błąd lub rozłączy
                done, pending = await asyncio.wait(
                    [recv_task, send_task, heartbeat_task],
                    return_when=asyncio.FIRST_EXCEPTION
                )

                for task in pending:
                    task.cancel()

            except (ConnectionError, OSError, asyncio.TimeoutError) as err:
                logger.warning(f"Błąd połączenia ({err}). Inicjalizacja rekonwersji...")
            except Exception as e:
                logger.error(f"Błąd krytyczny łącza: {e}")
            finally:
                if self._ws_client:
                    await self._ws_client.close()
                    self._ws_client = None

            if not self._running:
                break

            # Obliczenie opóźnienia exponential backoff z jitterem
            attempt += 1
            self.metrics.reconnect_count += 1
            self._set_state(ConnectionState.RECONNECTING)

            delay = min(
                self.config.reconnect_max_delay,
                self.config.reconnect_base_delay * (self.config.reconnect_factor ** (attempt - 1))
            )
            # Jitter: losowe wahanie ±20%
            delay = delay * (0.8 + 0.4 * random.random())

            await asyncio.sleep(delay)

    # ==========================================
    # PĘTLE ROBOCZE: ODBIÓR, WYSYŁKA, HEARTBEAT
    # ==========================================

    async def _receive_loop(self) -> None:
        """Asynchroniczny nasłuch i dekodowanie ramek przychodzących"""
        while self._running and self._ws_client and self._ws_client.is_connected:
            opcode, data = await self._ws_client.receive_frame()
            self.metrics.record_received(len(data))

            if opcode == OP_TEXT:
                text_payload = data.decode("utf-8")
                try:
                    packet = Packet.from_json(text_payload)
                    self._handle_incoming_packet(packet)
                except Exception as e:
                    logger.warning(f"Otrzymano niepoprawny pakiet JSON: {e} | Dane: {text_payload}")

            elif opcode == OP_PONG:
                self.metrics.record_pong()

            elif opcode == OP_PING:
                await self._ws_client.send_pong(data)

            elif opcode == OP_CLOSE:
                logger.info("Serwer zażądał zamknięcia połączenia (OP_CLOSE).")
                break

    async def _send_loop(self) -> None:
        """Konsumpcja kolejki wychodzącej i wysyłka do gniazda WebSocket"""
        while self._running and self._ws_client and self._ws_client.is_connected:
            packet: Packet = await self._send_queue.get()
            try:
                raw_json = packet.to_json()
                bytes_sent = await self._ws_client.send_text(raw_json)
                self.metrics.record_sent(bytes_sent)
            finally:
                self._send_queue.task_done()

    async def _heartbeat_loop(self) -> None:
        """Pętla czuwania Heartbeat / Ping-Pong Watchdog"""
        while self._running and self._ws_client and self._ws_client.is_connected:
            await asyncio.sleep(self.config.heartbeat_interval)

            if not self._ws_client or not self._ws_client.is_connected:
                break

            self.metrics.last_ping_time = time.time()
            # Wysyłamy ping zarówno na poziomie protokołu Voxen jak i ramki WebSocket
            await self._ws_client.send_ping(b"vx_ping")
            await self._send_packet_internal(PacketFactory.ping())

    # ==========================================
    # WEWNĘTRZNA OBSŁUGA PAKIETÓW & EVENT DISPATCH
    # ==========================================

    def _handle_incoming_packet(self, packet: Packet) -> None:
        """Przetwarza pakiety systemowe oraz powiadamia subskrybentów"""
        # Obsługa wbudowanych pakietów kontrolnych
        if packet.type == PacketType.HEARTBEAT_PONG:
            self.metrics.record_pong()

        elif packet.type == PacketType.AUTH_RESPONSE:
            success = packet.payload.get("success", False)
            if success:
                self._set_state(ConnectionState.AUTHENTICATED)
            else:
                self._set_state(ConnectionState.FAILED)

        # Powiadom zarejestrowanych słuchaczy dla danego typu pakietu
        pkt_type_str = packet.type.value if isinstance(packet.type, PacketType) else packet.type
        listeners = self._listeners.get(pkt_type_str, [])
        for listener in listeners:
            self._dispatch_to_ui(listener, packet)

        # Powiadom słuchaczy uniwersalnych (np. "*" / ALL)
        for listener in self._listeners.get("*", []):
            self._dispatch_to_ui(listener, packet)

    def _dispatch_to_ui(self, callback: Callable, *args: Any) -> None:
        """
        Bezpiecznie przekazuje wywołanie zwrotne do głównego wątku UI.
        Jeśli ui_dispatcher został skonfigurowany (np. app.after(0, ...)),
        wywołanie nastąpi w pętli Tkintera.
        """
        if self.ui_dispatcher:
            try:
                self.ui_dispatcher(callback, *args)
            except Exception as e:
                logger.error(f"Błąd delegacji do wątku UI: {e}")
        else:
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"Błąd w callbacku listenera: {e}")

    def _set_state(self, new_state: ConnectionState) -> None:
        """Atomowa zmiana stanu i notyfikacja słuchaczy stanu"""
        with self._state_lock:
            if self.metrics.state == new_state:
                return
            self.metrics.state = new_state

        for listener in self._state_listeners:
            self._dispatch_to_ui(listener, new_state)

    async def _send_packet_internal(self, packet: Packet) -> None:
        if self._send_queue:
            await self._send_queue.put(packet)

    # ==========================================
    # PUBLICZNE API DLA KONTROLERÓW / UI
    # ==========================================

    def set_ui_dispatcher(self, dispatcher: Callable[[Callable, Any], None]) -> None:
        """Rejestruje funkcję dyspozytora UI (np. app.after_idle)"""
        self.ui_dispatcher = dispatcher

    def on(self, packet_type: PacketType | str, callback: Callable[[Packet], None]) -> None:
        """
        Rejestruje listener na określony typ pakietu.
        Przykład: client.on(PacketType.MESSAGE_RECV, self.on_message_received)
        """
        key = packet_type.value if isinstance(packet_type, PacketType) else packet_type
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)

    def on_state_change(self, callback: Callable[[ConnectionState], None]) -> None:
        """Rejestruje listener zmiany stanu połączenia"""
        self._state_listeners.append(callback)

    def send_packet(self, packet: Packet) -> bool:
        """
        Wątkowo-bezpieczne wysyłanie pakietu z dowolnego wątku (np. z kontrolera UI).
        """
        if not self._loop or not self._running or not self._send_queue:
            return False

        asyncio.run_coroutine_threadsafe(
            self._send_queue.put(packet),
            self._loop
        )
        return True

    def authenticate(self, auth_key: str) -> None:
        """Wysyła żądanie autentykacji i zapamiętuje klucz na wypadek reconnect"""
        self._cached_auth_key = auth_key
        self._set_state(ConnectionState.AUTHENTICATING)
        self.send_packet(PacketFactory.auth(auth_key))

    def send_message(self, target: str, content: str, sender: str = "User", is_dm: bool = True) -> bool:
        """Wygodna metoda do wysyłania wiadomości tekstowej"""
        packet = PacketFactory.chat_message(
            sender=sender,
            recipient_or_channel=target,
            content=content,
            is_dm=is_dm
        )
        return self.send_packet(packet)

    def send_status(self, user: str, status: str, custom_status: str = "") -> bool:
        """Wysyła aktualizację statusu użytkownika"""
        packet = PacketFactory.status_update(user, status, custom_status)
        return self.send_packet(packet)

    def send_typing(self, user: str, target: str, is_typing: bool) -> bool:
        """Wysyła wskaźnik pisania"""
        packet = PacketFactory.typing(user, target, is_typing)
        return self.send_packet(packet)
