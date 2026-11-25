"""
INTEGRATION TEST - MESSAGE SEARCH AND HISTORY FILTERING
"""

import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import DatabaseManager
from models.chat_model import ChatModel


def test_message_search():
    print("=== TEST WYSZUKIWANIA I FILTROWANIA HISTORII ===")
    test_db = "test_message_search.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            Path(p).unlink()

    db = DatabaseManager(db_path=test_db)
    model = ChatModel(db=db)

    model.save_message("Tester", "Unity Bot", "Witaj w projekcie", packet_id="search-1", timestamp="10:15")
    model.save_message("Unity Bot", "Tester", "Projekt jest gotowy", packet_id="search-2", timestamp="10:30")
    model.save_message("Tester", "Unity Bot", "Spotkajmy sie o 10:45", packet_id="search-3", timestamp="10:45")

    all_results = model.search_history("Unity Bot", "Tester")
    assert len(all_results) >= 3

    content_results = model.search_messages(
        conversation="Unity Bot",
        current_user="Tester",
        query="projekt"
    )
    assert content_results
    assert any("projekt" in row["content"].lower() for row in content_results)

    sender_results = model.search_history(
        conversation="Unity Bot",
        current_user="Tester",
        sender="Unity"
    )
    assert sender_results
    assert all(row["sender"] == "Unity Bot" for row in sender_results)

    timestamp_results = model.search_history(
        conversation="Unity Bot",
        current_user="Tester",
        timestamp="10:45"
    )
    assert len(timestamp_results) == 1
    assert timestamp_results[0]["content"] == "Spotkajmy sie o 10:45"

    channel_id = model.save_message(
        "Tester",
        "Gaming#gry-pc",
        "Szukam drużyny",
        packet_id="channel-search",
        is_dm=False,
        timestamp="11:00"
    )
    assert channel_id > 0
    channel_results = model.search_history(
        conversation="Gaming#gry-pc",
        current_user="Tester",
        query="drużyny"
    )
    assert len(channel_results) == 1

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY WYSZUKIWANIA ZAKOŃCZONE SUKCESSEM! ===")


if __name__ == "__main__":
    test_message_search()
