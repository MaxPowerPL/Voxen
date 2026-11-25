"""
INTEGRATION TEST - MEMBER ACTIVITY AND MODERATION LOGS
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


def test_member_activity_logs():
    print("=== TEST DZIENNIKA AKTYWNOŚCI CZŁONKÓW ===")
    test_db = "test_member_activity_logs.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    for number in (1, 2, 3):
        success, _ = db.create_user(
            email=f"log{number}@voxen.dev",
            password="password",
            username=f"LogUser{number}"
        )
        assert success

    success, server = model.create_server(
        name="Audit Guild",
        icon="📋",
        owner_id=1
    )
    assert success
    server_id = server["id"]
    member_id = db.get_user_by_email("log2@voxen.dev")["id"]

    add_ok, _ = model.add_member(server_id, member_id, "member")
    assert add_ok
    log_id = model.log_activity(
        server_id,
        1,
        "member_added",
        member_id,
        "Role set to member"
    )
    assert log_id > 0

    role_ok, _ = model.set_member_role(
        server_id,
        member_id,
        "moderator",
        1
    )
    assert role_ok

    timeout_ok, expires_at = model.timeout_member(server_id, member_id, 10)
    assert timeout_ok
    model.log_activity(
        server_id,
        1,
        "member_timeout",
        member_id,
        f"Timeout expires at {expires_at}"
    )

    remove_ok, _ = model.remove_member(server_id, member_id)
    assert remove_ok
    model.log_activity(
        server_id,
        1,
        "member_removed",
        member_id,
        "Member removed"
    )

    logs = model.get_activity_logs(server_id, limit=50)
    actions = [entry["action"] for entry in logs]
    assert "member_added" in actions
    assert "role_changed" in actions
    assert "member_timeout" in actions
    assert "member_removed" in actions

    latest = logs[0]
    assert latest["target_user_id"] == member_id

    limited = model.get_activity_logs(server_id, limit=2)
    assert len(limited) == 2

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY DZIENNIKA AKTYWNOŚCI ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_member_activity_logs()
