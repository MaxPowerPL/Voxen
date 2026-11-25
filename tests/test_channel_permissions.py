"""
INTEGRATION TEST - CHANNEL PERMISSIONS AND ROLE OVERRIDES
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


def test_channel_permissions():
    print("=== TEST UPRAWNIEŃ POSZCZEGÓLNYCH KANAŁÓW ===")
    test_db = "test_channel_permissions.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    for number in (1, 2, 3, 4):
        success, _ = db.create_user(
            email=f"channel{number}@voxen.dev",
            password="password",
            username=f"ChannelUser{number}"
        )
        assert success

    success, server = model.create_server(
        name="Permission Guild",
        icon="🔐",
        owner_id=1
    )
    assert success
    server_id = server["id"]
    channels = model.get_channels(server_id)
    channel_id = channels[0]["id"]

    assert model.can_access_channel(channel_id, "owner", "view")
    assert model.can_access_channel(channel_id, "admin", "send")
    assert model.can_access_channel(channel_id, "moderator", "send")
    assert model.can_access_channel(channel_id, "member", "send")
    assert not model.can_access_channel(channel_id, "member", "manage")

    denied, _ = model.set_channel_permission(
        channel_id,
        "member",
        "view",
        False
    )
    assert denied
    assert not model.can_access_channel(channel_id, "member", "view")

    denied_send, _ = model.set_channel_permission(
        channel_id,
        "member",
        "send",
        False
    )
    assert denied_send
    assert not model.can_access_channel(channel_id, "member", "send")

    allowed, _ = model.set_channel_permission(
        channel_id,
        "member",
        "send",
        True
    )
    assert allowed
    assert model.can_access_channel(channel_id, "member", "send")

    overrides = model.get_channel_permissions(channel_id)
    assert any(
        item["role"] == "member"
        and item["permission"] == "send"
        and item["allowed"] == 1
        for item in overrides
    )

    invalid_role, invalid_message = model.set_channel_permission(
        channel_id,
        "guest",
        "view",
        True
    )
    assert not invalid_role
    assert invalid_message

    accessible_owner = model.get_accessible_channels(server_id, "owner")
    accessible_member = model.get_accessible_channels(server_id, "member")
    assert channels[0]["id"] in [item["id"] for item in accessible_owner]

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY UPRAWNIEŃ KANAŁÓW ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_channel_permissions()
