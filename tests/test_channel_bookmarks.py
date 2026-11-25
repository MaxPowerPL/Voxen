"""
INTEGRATION TEST - CHANNEL BOOKMARKS
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


def test_channel_bookmarks():
    print("=== TEST ZAKŁADEK KANAŁÓW ===")
    test_db = "test_channel_bookmarks.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    success, _ = db.create_user(
        email="bookmark@voxen.dev",
        password="password",
        username="BookmarkUser"
    )
    assert success

    server_ok, server = model.create_server(
        name="Bookmark Guild",
        icon="⭐",
        owner_id=1
    )
    assert server_ok
    channel_ok, channel = model.create_channel(
        server_id=server["id"],
        name="ulubiony",
        topic="Najczęściej używany kanał",
        channel_type="text",
        actor_id=1
    )
    assert channel_ok
    channel_id = channel["id"]

    assert not model.is_channel_bookmarked(channel_id, "BookmarkUser")
    add_ok, add_result = model.toggle_channel_bookmark(
        channel_id,
        "BookmarkUser"
    )
    assert add_ok
    assert add_result["bookmarked"] is True
    assert model.is_channel_bookmarked(channel_id, "BookmarkUser")

    bookmarks = model.get_channel_bookmarks("BookmarkUser")
    assert len(bookmarks) == 1
    assert bookmarks[0]["channel_id"] == channel_id
    assert bookmarks[0]["channel_name"] == "ulubiony"
    assert bookmarks[0]["server_name"] == "Bookmark Guild"

    remove_ok, remove_result = model.toggle_channel_bookmark(
        channel_id,
        "BookmarkUser"
    )
    assert remove_ok
    assert remove_result["bookmarked"] is False
    assert not model.is_channel_bookmarked(channel_id, "BookmarkUser")
    assert model.get_channel_bookmarks("BookmarkUser") == []

    missing_ok, missing_message = model.toggle_channel_bookmark(
        999999,
        "BookmarkUser"
    )
    assert not missing_ok
    assert missing_message

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY ZAKŁADEK KANAŁÓW ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_channel_bookmarks()
