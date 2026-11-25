"""
INTEGRATION TEST - SERVER WEBHOOK CONFIGURATION AND DELIVERY QUEUE
"""

import hashlib
import hmac
import json
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import DatabaseManager
from models.server_model import ServerModel


def test_server_webhooks():
    print("=== TEST WEBHOOKÓW SERWEROWYCH ===")
    test_db = "test_server_webhooks.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    success, server = model.create_server(
        name="Webhook Guild",
        icon="🔗",
        owner_id=1
    )
    assert success
    server_id = server["id"]

    invalid_url, _ = model.create_webhook(
        server_id,
        "Niepoprawny",
        "ftp://example.com/hook"
    )
    assert not invalid_url

    webhook_ok, webhook = model.create_webhook(
        server_id,
        "Audit Hook",
        "https://example.com/webhook",
        secret="test-secret",
        events="member.added,message.created"
    )
    assert webhook_ok
    assert webhook["is_active"] is True

    webhooks = model.get_webhooks(server_id)
    assert len(webhooks) == 1
    assert webhooks[0]["secret"] == "test-secret"

    deliveries = model.dispatch_webhook(
        server_id,
        "member.added",
        {"user_id": 2, "role": "member"}
    )
    assert len(deliveries) == 1
    assert deliveries[0]["status"] == "queued"

    delivery_list = model.get_webhook_deliveries(server_id)
    assert len(delivery_list) == 1
    payload = delivery_list[0]["payload"]
    signature = delivery_list[0]["signature"]
    expected = hmac.new(
        b"test-secret",
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(signature, expected)

    decoded = json.loads(payload)
    assert decoded["event"] == "member.added"
    assert decoded["server_id"] == server_id

    filtered = model.dispatch_webhook(
        server_id,
        "server.created",
        {"name": "Ignored event"}
    )
    assert filtered == []

    assert model.set_webhook_active(webhook["id"], False)
    inactive_deliveries = model.dispatch_webhook(
        server_id,
        "message.created",
        {"message_id": 10}
    )
    assert inactive_deliveries == []

    assert model.delete_webhook(webhook["id"])
    assert model.get_webhooks(server_id) == []

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY WEBHOOKÓW SERWEROWYCH ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_server_webhooks()
