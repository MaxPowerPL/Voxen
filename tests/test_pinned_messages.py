"""
INTEGRATION TEST - PINNED MESSAGES
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


def test_pinned_messages():
    print("=== TEST PRZYPINANIA WIADOMOŚCI ===")
    test_db = "test_pinned_messages.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ChatModel(db=db)

    message_one = model.save_message(
        sender="Tester",
        target="Unity Bot",
        content="Ważna wiadomość pierwsza",
        packet_id="pinned-message-1",
        is_dm=True
    )
    message_two = model.save_message(
        sender="Unity Bot",
        target="Tester",
        content="Ważna wiadomość druga",
        packet_id="pinned-message-2",
        is_dm=True
    )
    assert message_one > 0
    assert message_two > 0

    success, pin = model.pin_message(
        message_one,
        "Unity Bot",
        "Tester"
    )
    assert success
    assert pin["message_id"] == message_one
    assert model.is_message_pinned(message_one)
    assert not model.is_message_pinned(message_two)

    pinned = model.get_pinned_messages("Unity Bot")
    assert len(pinned) == 1
    assert pinned[0]["content"] == "Ważna wiadomość pierwsza"
    assert pinned[0]["pinned_by"] == "Tester"
    assert pinned[0]["is_pinned"] is True

    history = model.get_history("Unity Bot", "Tester")
    pinned_history = next(item for item in history if item["id"] == message_one)
    assert pinned_history["is_pinned"] is True

    duplicate_success, _ = model.pin_message(
        message_one,
        "Unity Bot",
        "Tester"
    )
    assert duplicate_success
    assert len(model.get_pinned_messages("Unity Bot")) == 1

    missing = model.pin_message(999999, "Unity Bot", "Tester")
    assert missing[0] is False

    assert model.unpin_message(message_one)
    assert not model.is_message_pinned(message_one)
    assert model.get_pinned_messages("Unity Bot") == []

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY PRZYPINANIA WIADOMOŚCI ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_pinned_messages()
