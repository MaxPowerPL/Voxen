"""
INTEGRATION TEST - SERVER ANALYTICS
"""

import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import DatabaseManager
from models.server_model import ServerModel
from models.chat_model import ChatModel


def test_server_analytics():
    print("=== TEST ANALITYKI SERWERA ===")
    test_db = "test_server_analytics.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    server_model = ServerModel(db=db)
    chat_model = ChatModel(db=db)

    for number in (1, 2, 3):
        success, _ = db.create_user(
            email=f"analytics{number}@voxen.dev",
            password="password",
            username=f"AnalyticsUser{number}"
        )
        assert success

    success, server = server_model.create_server(
        name="Analytics Guild",
        icon="📊",
        owner_id=1
    )
    assert success
    server_id = server["id"]

    member_id = db.get_user_by_email("analytics2@voxen.dev")["id"]
    assert server_model.add_member(server_id, member_id, "member")[0]
    success, channel = server_model.create_channel(
        server_id=server_id,
        name="metrics",
        topic="Analytics",
        actor_id=1
    )
    assert success

    chat_model.save_message(
        sender="AnalyticsUser2",
        target="Analytics Guild#ogólny",
        content="Pierwsza wiadomość",
        packet_id="analytics-message-1",
        is_dm=False
    )
    chat_model.save_message(
        sender="AnalyticsUser2",
        target="Analytics Guild#metrics",
        content="Druga wiadomość",
        packet_id="analytics-message-2",
        is_dm=False
    )

    analytics = server_model.get_analytics(server_id)
    assert analytics["server_name"] == "Analytics Guild"
    assert analytics["channel_count"] == 2
    assert analytics["member_count"] == 2
    assert analytics["message_count"] == 2
    assert analytics["role_counts"]["owner"] == 1
    assert analytics["role_counts"]["member"] == 1

    missing = server_model.get_analytics(999999)
    assert missing["server_name"] == ""
    assert missing["channel_count"] == 0
    assert missing["message_count"] == 0

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY ANALITYKI SERWERA ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_server_analytics()
