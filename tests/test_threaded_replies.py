"""
INTEGRATION TEST - THREADED REPLY CONTEXT
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


def test_threaded_replies():
    print("=== TEST ODPOWIEDZI WĄTKOWYCH ===")
    test_db = "test_threaded_replies.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ChatModel(db=db)

    root_id = model.save_message(
        sender="Tester",
        target="Unity Bot",
        content="Pytanie główne",
        packet_id="thread-root-1",
        is_dm=True
    )
    second_root_id = model.save_message(
        sender="Unity Bot",
        target="Tester",
        content="Drugi niezależny wątek",
        packet_id="thread-root-2",
        is_dm=True
    )
    assert root_id > 0
    assert second_root_id > 0

    reply_one = model.save_message(
        sender="Unity Bot",
        target="Tester",
        content="Pierwsza odpowiedź",
        packet_id="thread-reply-1",
        is_dm=True,
        reply_to_message_id=root_id
    )
    reply_two = model.save_message(
        sender="Tester",
        target="Unity Bot",
        content="Dalsza odpowiedź",
        packet_id="thread-reply-2",
        is_dm=True,
        reply_to_message_id=root_id
    )
    other_reply = model.save_message(
        sender="Tester",
        target="Unity Bot",
        content="Odpowiedź do drugiego root",
        packet_id="thread-reply-3",
        is_dm=True,
        reply_to_message_id=second_root_id
    )
    assert reply_one > 0
    assert reply_two > 0
    assert other_reply > 0

    root_replies = model.get_thread_replies(root_id)
    assert len(root_replies) == 2
    assert {reply["content"] for reply in root_replies} == {
        "Pierwsza odpowiedź",
        "Dalsza odpowiedź"
    }

    second_replies = model.get_thread_replies(second_root_id)
    assert len(second_replies) == 1
    assert second_replies[0]["content"] == "Odpowiedź do drugiego root"

    own_context = model.get_reply_context(reply_one)
    assert own_context["id"] == reply_one

    root_context = model.get_reply_context(root_id)
    assert root_context["content"] == "Pytanie główne"

    history = model.get_history("Unity Bot", "Tester")
    reply_row = next(item for item in history if item["id"] == reply_one)
    assert reply_row["reply_to_message_id"] == root_id
    assert reply_row["reply_context"]["content"] == "Pytanie główne"

    missing_context = model.get_reply_context(999999)
    assert missing_context is None

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY ODPOWIEDZI WĄTKOWYCH ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_threaded_replies()
