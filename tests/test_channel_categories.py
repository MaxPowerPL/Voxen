"""
INTEGRATION TEST - CHANNEL CATEGORIES
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


def test_channel_categories():
    print("=== TEST KATEGORII KANAŁÓW ===")
    test_db = "test_channel_categories.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    success, server = model.create_server(
        name="Category Guild",
        icon="📁",
        owner_id=1
    )
    assert success
    server_id = server["id"]

    category_ok, community = model.create_category(
        server_id,
        "Społeczność",
        position=1
    )
    assert category_ok
    category_ok, voice = model.create_category(
        server_id,
        "Głosowe",
        position=2
    )
    assert category_ok

    text_ok, text_channel = model.create_channel(
        server_id=server_id,
        name="ogłoszenia",
        topic="Wiadomości",
        channel_type="text",
        actor_id=1
    )
    assert text_ok
    voice_ok, voice_channel = model.create_channel(
        server_id=server_id,
        name="lobby",
        topic="Rozmowy",
        channel_type="voice",
        actor_id=1
    )
    assert voice_ok

    assert model.assign_channel_category(text_channel["id"], community["id"])
    assert model.assign_channel_category(voice_channel["id"], voice["id"])

    categories = model.get_categories(server_id)
    assert [category["name"] for category in categories] == ["Społeczność", "Głosowe"]

    grouped = model.get_grouped_channels(server_id)
    community_channels = grouped[str(community["id"])]["channels"]
    voice_channels = grouped[str(voice["id"])]["channels"]
    assert any(channel["name"] == "ogłoszenia" for channel in community_channels)
    assert any(channel["name"] == "lobby" for channel in voice_channels)

    assert model.set_category_collapsed(community["id"], True)
    collapsed = model.get_categories(server_id)
    community_state = next(
        category for category in collapsed
        if category["id"] == community["id"]
    )
    assert community_state["collapsed"] is True

    duplicate_ok, duplicate_message = model.create_category(
        server_id,
        "Społeczność",
        position=3
    )
    assert not duplicate_ok
    assert duplicate_message

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY KATEGORII KANAŁÓW ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_channel_categories()
