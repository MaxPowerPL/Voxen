"""
INTEGRATION TEST - VOICE/AUDIO CHANNEL MOCK STATE
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


def test_voice_channels():
    print("=== TEST KANAŁÓW GŁOSOWYCH (MOCK/SKELETON) ===")
    test_db = "test_voice_channels.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    success, _ = db.create_user(
        email="voice@voxen.dev",
        password="password",
        username="VoiceUser"
    )
    assert success

    success, server = model.create_server(
        name="Voice Guild",
        icon="🎙",
        owner_id=1
    )
    assert success
    server_id = server["id"]

    text_ok, text_channel = model.create_channel(
        server_id=server_id,
        name="dyskusje",
        topic="Kanał tekstowy",
        channel_type="text",
        actor_id=1
    )
    assert text_ok

    voice_ok, voice_channel = model.create_channel(
        server_id=server_id,
        name="lobby",
        topic="Kanał głosowy",
        channel_type="voice",
        actor_id=1
    )
    assert voice_ok
    assert voice_channel["channel_type"] == "voice"

    denied, denied_message = model.join_voice_channel(
        text_channel["id"],
        "VoiceUser"
    )
    assert not denied
    assert "głosowym" in denied_message

    joined, participant = model.join_voice_channel(
        voice_channel["id"],
        "VoiceUser",
        muted=False,
        deafened=False
    )
    assert joined
    assert participant["user_name"] == "VoiceUser"

    participants = model.get_voice_participants(voice_channel["id"])
    assert len(participants) == 1
    assert participants[0]["user_name"] == "VoiceUser"
    assert participants[0]["muted"] is False
    assert participants[0]["deafened"] is False

    muted_joined, muted_participant = model.join_voice_channel(
        voice_channel["id"],
        "VoiceUser",
        muted=True,
        deafened=False
    )
    assert muted_joined
    assert muted_participant["muted"] is True

    assert model.leave_voice_channel(
        voice_channel["id"],
        "VoiceUser"
    )
    assert model.get_voice_participants(voice_channel["id"]) == []

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY KANAŁÓW GŁOSOWYCH ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_voice_channels()
