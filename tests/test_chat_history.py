"""
INTEGRATION TEST - VOXEN PERSISTENT CHAT HISTORY (SQLITE WAL)
Weryfikacja: zapisu wiadomości, filtrowania par DM, zapobiegania duplikatom (packet_id)
i integracji z wirtualnym widokiem czatu.
"""

import io
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import DatabaseManager
from models.chat_model import ChatModel


def test_persistent_chat_history():
    print("=== TEST TRWAŁEJ HISTORII WIADOMOŚCI CZATU W SQLITE ===")
    test_db = "test_chat_history.db"

    # Sprzątanie przed testem
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass

    db = DatabaseManager(db_path=test_db)
    chat_model = ChatModel(db=db)

    # 1. Zapis wiadomości w dwóch kierunkach (DM między 'UserA' a 'UserB')
    print(" [1/5] Zapisywanie wiadomości do bazy SQLite...")
    msg1_id = chat_model.save_message(
        sender="UserA",
        target="UserB",
        content="Cześć UserB! Jak tam projekt?",
        packet_id="uuid-msg-001",
        timestamp="14:00"
    )
    msg2_id = chat_model.save_message(
        sender="UserB",
        target="UserA",
        content="Siema! Właśnie testuję trwałą historię SQLite.",
        packet_id="uuid-msg-002",
        timestamp="14:01"
    )
    msg3_id = chat_model.save_message(
        sender="UserA",
        target="UserB",
        content="Działa wyśmienicie w trybie WAL!",
        packet_id="uuid-msg-003",
        timestamp="14:02"
    )
    print(f"       Zapisano 3 wiadomości (ID: {msg1_id}, {msg2_id}, {msg3_id})")
    assert msg1_id > 0 and msg2_id > 0 and msg3_id > 0

    # 2. Zapobieganie duplikatom (Idempotencja przez packet_id)
    print(" [2/5] Weryfikacja idempotencji i blokowania duplikatów (packet_id)...")
    dup_id = chat_model.save_message(
        sender="UserA",
        target="UserB",
        content="Cześć UserB! Jak tam projekt?",
        packet_id="uuid-msg-001"  # Ten sam packet_id!
    )
    # Z INSERT OR IGNORE, duplikat nie tworzy nowego rekordu
    history_after_dup = chat_model.get_history("UserB", "UserA")
    assert len(history_after_dup) == 3, f"Oczekiwano 3 wiadomości, a jest {len(history_after_dup)}"
    print(" [OK] Blokada duplikatów pakietów: SUKCES (Idempotencja zachowana)")

    # 3. Pobranie historii i weryfikacja chronologii oraz flag is_own / is_bot
    print(" [3/5] Pobranie historii konwersacji z punktu widzenia 'UserA'...")
    history = chat_model.get_history(conversation="UserB", current_user="UserA")
    assert len(history) == 3
    assert history[0]["content"] == "Cześć UserB! Jak tam projekt?"
    assert history[0]["is_own"] is True
    assert history[1]["content"] == "Siema! Właśnie testuję trwałą historię SQLite."
    assert history[1]["is_own"] is False
    assert history[2]["content"] == "Działa wyśmienicie w trybie WAL!"
    assert history[2]["is_own"] is True
    print(" [OK] Chronologia i flagi is_own dla 'UserA': SUKCES")

    # 4. Pobranie historii z punktu widzenia 'UserB' (symetria)
    print(" [4/5] Pobranie historii z punktu widzenia rozmówcy 'UserB'...")
    history_user_b = chat_model.get_history(conversation="UserA", current_user="UserB")
    assert len(history_user_b) == 3
    assert history_user_b[0]["is_own"] is False
    assert history_user_b[1]["is_own"] is True
    print(" [OK] Symetria relacji dwustronnej DM: SUKCES")

    # 5. Sprawdzenie izolacji konwersacji (Wiadomości do innego użytkownika nie mieszają się)
    print(" [5/5] Weryfikacja izolacji wątków...")
    chat_model.save_message(sender="Nemeczek", target="UserA", content="Gramy coś?")
    history_nemeczek = chat_model.get_history(conversation="Nemeczek", current_user="UserA")
    assert len(history_nemeczek) == 1
    assert history_nemeczek[0]["content"] == "Gramy coś?"

    # Ponownie sprawdzamy UserB - nadal ma dokładnie 3
    assert len(chat_model.get_history("UserB", "UserA")) == 3
    print(" [OK] Izolacja konwersacji: SUKCES")

    # Sprzątanie
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass

    print("\n=== WSZYSTKIE TESTY HISTORII CZATU W SQLITE ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_persistent_chat_history()
