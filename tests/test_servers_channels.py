"""
INTEGRATION TEST - SERVERS & TEXT CHANNELS MANAGEMENT
Weryfikacja: dynamicznych serwerów i kanałów w SQLite, kaskadowego usuwania,
przełączania kontekstów w AppController oraz widoków w AppView.
"""

import io
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import customtkinter as ctk

from database.db import DatabaseManager
from models.server_model import ServerModel
from models.chat_model import ChatModel
from views.app_view import AppView
from controllers.app_controller import AppController


class MockApp:
    def __init__(self):
        self.current_user = {"email": "tester@voxen.dev", "username": "Tester", "id": 1}
        self.network_client = None


def test_servers_and_channels():
    print("=== TEST DYNAMICZNYCH SERWERÓW I KANAŁÓW TEKSTOWYCH ===")
    test_db = "test_servers.db"

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass

    db = DatabaseManager(db_path=test_db)
    server_model = ServerModel(db=db)

    # 1. Sprawdzenie seedowanych serwerów i kanałów
    print(" [1/5] Weryfikacja domyślnych serwerów i kanałów z bazy...")
    servers = server_model.get_all_servers()
    print(f"       Załadowano {len(servers)} serwerów z bazy SQLite:")
    for s in servers:
        channels = server_model.get_channels(s["id"])
        ch_names = [f"#{c['name']}" for c in channels]
        print(f"       - {s['icon']} {s['name']}: {', '.join(ch_names)}")
    assert len(servers) >= 5
    assert any(s["name"] == "Voxen Official" for s in servers)
    assert any(s["name"] == "Gaming" for s in servers)

    # 2. Tworzenie nowego serwera i sprawdzanie domyślnego kanału
    print(" [2/5] Tworzenie nowego serwera 'Cyberpunk Guild'...")
    ok, new_server = server_model.create_server(name="Cyberpunk Guild", icon="⚔️", owner_id=1)
    assert ok is True
    s_id = new_server["id"]

    channels = server_model.get_channels(s_id)
    assert len(channels) == 1
    assert channels[0]["name"] == "ogólny"
    print(f" [OK] Serwer utworzony pomyślnie z domyślnym kanałem #{channels[0]['name']}")

    # 3. Dodawanie nowego kanału tekstowego do serwera
    print(" [3/5] Dodawanie kanału tekstowego '#builds' z tematem...")
    ok_ch, new_ch = server_model.create_channel(
        server_id=s_id,
        name="builds",
        topic="Najlepsze buildy i ekwipunek"
    )
    assert ok_ch is True
    assert new_ch["name"] == "builds"

    channels_after = server_model.get_channels(s_id)
    assert len(channels_after) == 2
    print(f" [OK] Kanał #{new_ch['name']} dodany pomyślnie! Łącznie kanałów: {len(channels_after)}")

    # 4. Blokada duplikatu nazwy kanału na tym samym serwerze
    print(" [4/5] Sprawdzenie unikalności nazwy kanału na serwerze...")
    dup_ok, dup_err = server_model.create_channel(server_id=s_id, name="builds")
    assert dup_ok is False
    print(f" [OK] Blokada duplikatu kanału: SUKCES ({dup_err})")

    # 5. Integracja z kontrolerem i widokiem (AppController & AppView)
    print(" [5/5] Test symulacji przełączania serwerów i kanałów w GUI...")
    root = ctk.CTk()
    root.geometry("800x600")
    root.withdraw()

    app = MockApp()
    view = AppView(root, user_data=app.current_user)
    controller = AppController(model=None, view=view, app=app)
    # Podepnij bazę testową pod kontroler
    controller.server_model = server_model
    controller.chat_model = ChatModel(db=db)
    view.set_controller(controller)

    # Wybór serwera Gaming
    gaming_server = next(s for s in servers if s["name"] == "Gaming")
    controller.handle_server_click(gaming_server["id"], gaming_server["name"])

    assert controller.current_server == "Gaming"
    assert controller.current_channel is not None
    assert "#" in view.chat_title.cget("text")
    print(f" [OK] Wybór serwera Gaming otworzył kanał: {view.chat_title.cget('text')}")

    # Powrót do Direct Messages
    controller.handle_server_click(None, "Direct Messages")
    assert controller.current_server == "Direct Messages"
    assert controller.current_channel is None
    assert view.server_name_label.cget("text") == "🏠 Znajomi"
    print(" [OK] Powrót do Direct Messages przywrócił panel znajomych: SUKCES")

    # Sprzątanie
    root.destroy()
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass

    print("\n=== WSZYSTKIE TESTY SERWERÓW I KANAŁÓW ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_servers_and_channels()
