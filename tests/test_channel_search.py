"""
INTEGRATION TEST - CHANNEL SEARCH AND SORTING
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


def test_channel_search():
    print("=== TEST WYSZUKIWANIA I SORTOWANIA KANAŁÓW ===")
    test_db = "test_channel_search.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    ok, _ = db.create_user(
        email="channel-search@voxen.dev",
        password="password",
        username="ChannelSearch"
    )
    assert ok

    success, server = model.create_server(
        name="Search Guild",
        icon="🔎",
        owner_id=1
    )
    assert success
    server_id = server["id"]

    ok, _ = model.create_channel(
        server_id=server_id,
        name="zeta",
        topic="Zaawansowane projekty",
        actor_id=1
    )
    assert ok
    ok, _ = model.create_channel(
        server_id=server_id,
        name="alpha",
        topic="Szybkie dyskusje",
        actor_id=1
    )
    assert ok
    ok, _ = model.create_channel(
        server_id=server_id,
        name="beta",
        topic="Ogólne projekty",
        actor_id=1
    )
    assert ok

    all_position = model.search_channels(server_id, sort_by="position")
    assert [channel["name"] for channel in all_position[:3]] == ["ogólny", "zeta", "alpha"]

    name_sorted = model.search_channels(server_id, sort_by="name")
    assert [channel["name"] for channel in name_sorted] == sorted(
        [channel["name"] for channel in name_sorted]
    )

    name_desc = model.search_channels(server_id, sort_by="name_desc")
    assert [channel["name"] for channel in name_desc] == sorted(
        [channel["name"] for channel in name_desc],
        reverse=True
    )

    by_name = model.search_channels(server_id, query="alp")
    assert len(by_name) == 1
    assert by_name[0]["name"] == "alpha"

    by_topic = model.search_channels(server_id, query="projekty")
    assert len(by_topic) == 2
    assert {channel["name"] for channel in by_topic} == {"zeta", "beta"}

    topic_sorted = model.search_channels(server_id, sort_by="topic")
    assert isinstance(topic_sorted, list)

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY WYSZUKIWANIA I SORTOWANIA KANAŁÓW ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_channel_search()
