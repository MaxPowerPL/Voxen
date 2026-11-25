"""
INTEGRATION TEST - SERVER ROLES AND PERMISSIONS
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


def test_server_roles():
    print("=== TEST RÓL I UPRAWNIEŃ SERWEROWYCH ===")
    test_db = "test_server_roles.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    for number in (1, 2, 3, 4):
        ok, _ = db.create_user(
            email=f"user{number}@voxen.dev",
            password="password",
            username=f"User{number}"
        )
        assert ok

    success, server = model.create_server(
        name="Role Guild",
        icon="🛡️",
        owner_id=1
    )
    assert success
    server_id = server["id"]

    assert model.get_member_role(server_id, 1) == "owner"
    assert model.can_manage(server_id, 1)
    assert model.can_moderate(server_id, 1)

    admin_ok, admin = model.set_member_role(server_id, 2, "admin")
    moderator_ok, moderator = model.set_member_role(server_id, 3, "moderator")
    member_ok, member = model.set_member_role(server_id, 4, "member")
    assert admin_ok and moderator_ok and member_ok

    assert model.get_member_role(server_id, 2) == "admin"
    assert model.can_manage(server_id, 2)
    assert model.can_moderate(server_id, 2)

    assert model.get_member_role(server_id, 3) == "moderator"
    assert not model.can_manage(server_id, 3)
    assert model.can_moderate(server_id, 3)

    assert model.get_member_role(server_id, 4) == "member"
    assert not model.can_manage(server_id, 4)
    assert not model.can_moderate(server_id, 4)

    denied, denied_message = model.create_channel(
        server_id=server_id,
        name="member-channel",
        actor_id=4
    )
    assert not denied
    assert "uprawnień" in denied_message

    allowed, channel = model.create_channel(
        server_id=server_id,
        name="admin-channel",
        actor_id=2
    )
    assert allowed

    channel_id = channel["id"]
    assert model.delete_channel(channel_id, actor_id=3) is False
    assert model.delete_channel(channel_id, actor_id=2) is True

    invalid_ok, invalid_message = model.set_member_role(server_id, 5, "invalid")
    assert not invalid_ok
    assert invalid_message

    available = model.get_available_users(server_id)
    assert isinstance(available, list)

    member_add_ok, _ = model.add_member(server_id, 4, "moderator")
    assert member_add_ok
    assert model.get_member_role(server_id, 4) == "moderator"

    remove_ok, remove_message = model.remove_member(server_id, 4)
    assert remove_ok
    assert remove_message
    owner_remove_ok, owner_remove_message = model.remove_member(server_id, 1)
    assert not owner_remove_ok
    assert owner_remove_message

    members = model.get_members(server_id)
    roles = {row["user_id"]: row["role"] for row in members}
    assert roles[1] == "owner"

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY RÓL I UPRAWNIEŃ ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_server_roles()
