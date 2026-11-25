"""
INTEGRATION TEST - MESSAGE MODERATION AND MEMBER TIMEOUT
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import DatabaseManager
from models.chat_model import ChatModel
from models.server_model import ServerModel


def test_moderation_tools():
    print("=== TEST NARZĘDZI MODERACYJNYCH ===")
    test_db = "test_moderation_tools.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    chat_model = ChatModel(db=db)
    server_model = ServerModel(db=db)

    ok, _ = db.create_user(
        email="moderator@voxen.dev",
        password="password",
        username="Moderator"
    )
    assert ok
    ok, _ = db.create_user(
        email="member@voxen.dev",
        password="password",
        username="Member"
    )
    assert ok

    success, server = server_model.create_server(
        name="Moderation Guild",
        icon="🛡️",
        owner_id=1
    )
    assert success
    server_id = server["id"]

    moderator_id = db.get_user_by_email("moderator@voxen.dev")["id"]
    member_id = db.get_user_by_email("member@voxen.dev")["id"]
    assert server_model.set_member_role(
        server_id,
        moderator_id,
        "moderator",
        1
    )[0]
    assert server_model.add_member(server_id, member_id, "member")[0]

    assert server_model.can_moderate(server_id, moderator_id)
    assert not server_model.can_moderate(server_id, member_id)

    message_id = chat_model.save_message(
        sender="Member",
        target=f"{server['name']}#ogólny",
        content="Wiadomość do moderacji",
        packet_id="moderation-message",
        is_dm=False
    )
    assert message_id > 0
    assert chat_model.delete_message(message_id)
    assert chat_model.get_history(
        f"{server['name']}#ogólny",
        "Member"
    ) == []

    timeout_ok, expires_at = server_model.timeout_member(
        server_id,
        member_id,
        15
    )
    assert timeout_ok
    timeout = server_model.get_member_timeout(server_id, member_id)
    assert timeout is not None
    assert timeout["expires_at"] == expires_at

    expires = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
    assert expires > datetime.now()

    expired_at = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    assert db.timeout_server_member(server_id, member_id, expired_at)
    assert server_model.get_member_timeout(server_id, member_id) is None

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY MODERACYJNE ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_moderation_tools()
