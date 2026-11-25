"""
INTEGRATION TEST - EMOJI PICKER AND MESSAGE REACTION CONTROLS
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
from network.protocol import PacketFactory, PacketType


def test_emoji_reactions():
    print("=== TEST WYBORU EMOJI I REAKCJI NA WIADOMOŚCI ===")
    test_db = "test_emoji_reactions.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ChatModel(db=db)
    message_id = model.save_message(
        sender="Tester",
        target="Unity Bot",
        content="Nowa wiadomość",
        packet_id="emoji-test-1",
        is_dm=True
    )
    assert message_id > 0

    active = db.toggle_message_reaction(message_id, "Tester", "👍")
    assert active is True
    reactions = db.get_message_reactions(message_id)
    assert reactions == [{"emoji": "👍", "count": 1}]

    active_again = db.toggle_message_reaction(message_id, "Tester", "👍")
    assert active_again is False
    assert db.get_message_reactions(message_id) == []

    db.toggle_message_reaction(message_id, "Tester", "🔥")
    db.toggle_message_reaction(message_id, "Unity Bot", "🔥")
    reactions = db.get_message_reactions(message_id)
    assert reactions == [{"emoji": "🔥", "count": 2}]

    history = model.get_history("Unity Bot", "Tester")
    message = next(item for item in history if item["id"] == message_id)
    assert message["reactions"] == [{"emoji": "🔥", "count": 2}]

    chat_packet = PacketFactory.chat_message(
        sender="Tester",
        recipient_or_channel="Unity Bot",
        content="Emoji test",
        is_dm=True
    )
    assert chat_packet.type == PacketType.MESSAGE_SEND

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY EMOJI I REAKCJI ZAKOŃCZONE SUKCESSEM! ===")


if __name__ == "__main__":
    test_emoji_reactions()
