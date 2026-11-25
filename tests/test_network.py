"""
INTEGRATION TEST - VOXEN NETWORK ENGINE
Weryfikacja: połączenia, autentykacji, heartbeat, wymiany wiadomości i poprawnego zamykania.
"""

import asyncio
import time
import sys
import io

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from network.client import NetworkClient
from network.connection import ConnectionConfig, ConnectionState
from network.mock_server import MockWebSocketServer
from network.protocol import PacketType, Packet


async def run_test():
    print("=== TEST SILNIKA SIECIOWEGO VOXEN ===")
    
    # 1. Uruchomienie lokalnego mock serwera
    server = MockWebSocketServer(host="127.0.0.1", port=8765)
    await server.start()
    print(" [1/5] Mock Server uruchomiony na 127.0.0.1:8765")

    # 2. Inicjalizacja i start klienta sieciowego
    config = ConnectionConfig(
        host="127.0.0.1",
        port=8765,
        heartbeat_interval=1.0,
        heartbeat_timeout=2.0
    )

    received_messages = []
    received_typing = []
    state_changes = []

    client = NetworkClient(config=config)
    
    client.on_state_change(lambda state: state_changes.append(state))
    client.on(PacketType.MESSAGE_RECV, lambda pkt: received_messages.append(pkt))
    client.on(PacketType.TYPING_START, lambda pkt: received_typing.append(pkt))

    client.start()
    print(" [2/5] Wątek klienta uruchomiony")

    # Poczekaj na nawiązanie połączenia
    timeout = 5.0
    start_t = time.time()
    while client.metrics.state not in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED):
        if time.time() - start_t > timeout:
            raise TimeoutError("Klient nie połączył się z serwerem w wyznaczonym czasie!")
        await asyncio.sleep(0.05)

    print(f" [3/5] Połączenie nawiązane! Stan: {client.metrics.state.value}")

    # 3. Autentykacja
    client.authenticate("tester@voxen.dev")
    await asyncio.sleep(0.2)
    assert client.metrics.state == ConnectionState.AUTHENTICATED, f"Błędny stan po auth: {client.metrics.state}"
    print(f" [4/5] Uwierzytelnienie udane! Stan: {client.metrics.state.value}")

    # 4. Wysłanie wiadomości do Unity Bot i oczekiwanie na symulację odpowiedzi
    print("       Wysyłanie wiadomości do 'Unity Bot'...")
    client.send_message(target="Unity Bot", content="Test silnika sieciowego!", sender="Tester")

    # Czekamy na odpowiedź bota (powinno zająć ~1-1.5s z symulacją pisania)
    start_t = time.time()
    while not received_messages:
        if time.time() - start_t > 5.0:
            raise TimeoutError("Nie odebrano odpowiedzi od bota!")
        await asyncio.sleep(0.05)

    reply_content = received_messages[0].payload.get("content", "")
    print(f" [5/5] Odebrano odpowiedź bota: '{reply_content}'")
    assert "Unity Bot" in received_messages[0].payload.get("sender", "")

    # Sprawdzenie metryk
    print(f"       Metryki: Pakiety wysłane: {client.metrics.packets_sent}, odebrane: {client.metrics.packets_received}")
    print(f"       Latencja ping: {client.metrics.latency_ms} ms")

    # Sprzątanie
    client.stop()
    await server.stop()
    print("=== WSZYSTKIE TESTY ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    asyncio.run(run_test())
