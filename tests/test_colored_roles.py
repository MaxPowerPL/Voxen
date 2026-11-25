"""
INTEGRATION TEST - COLORED AND RGB ROLES
"""

import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from utils import RGB_ROLE_COLORS
from database.db import DatabaseManager
from models.server_model import ServerModel
from controllers.app_controller import AppController


class TimerView:
    def __init__(self):
        self.cancelled = []

    def after_cancel(self, timer_id):
        self.cancelled.append(timer_id)


def test_colored_roles():
    print("=== TEST KOLOROWANYCH I RGB RÓL ===")
    test_db = "test_colored_roles.db"
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    assert len(RGB_ROLE_COLORS) == 20
    assert len(set(RGB_ROLE_COLORS)) == 20

    db = DatabaseManager(db_path=test_db)
    model = ServerModel(db=db)

    user_ok, owner = db.create_user(
        email="rgb-owner@voxen.dev",
        password="password",
        username="RGBOwner"
    )
    assert user_ok
    server_ok, server = model.create_server(
        name="RGB Guild",
        icon="🌈",
        owner_id=owner["id"]
    )
    assert server_ok
    server_id = server["id"]

    roles = model.get_roles(server_id)
    role_names = {role["name"] for role in roles}
    assert {"owner", "rgb", "admin", "moderator", "member"} <= role_names
    rgb_role = next(role for role in roles if role["name"] == "rgb")
    assert rgb_role["is_rgb"] is True
    assert rgb_role["rgb_interval_ms"] in (5000, 10000)

    color_ok, _ = model.update_role_color(
        server_id,
        "owner",
        "#ff6b35"
    )
    assert color_ok

    invalid_ok, invalid_message = model.update_role_color(
        server_id,
        "owner",
        "ff6b35"
    )
    assert not invalid_ok
    assert "HEX" in invalid_message

    rgb_ok, rgb_result = model.toggle_role_rgb(
        server_id,
        "rgb",
        True,
        10000
    )
    assert rgb_ok
    assert rgb_result["rgb_interval_ms"] == 10000

    invalid_rgb, invalid_rgb_message = model.toggle_role_rgb(
        server_id,
        "rgb",
        True,
        2500
    )
    assert not invalid_rgb
    assert "5000" in invalid_rgb_message

    owner_color = model.resolve_nickname_color(
        server_id,
        "RGBOwner"
    )
    assert owner_color["role"] == "owner"
    assert owner_color["color"] == "#ff6b35"
    assert owner_color["priority"] == 100

    dm_color = model.resolve_nickname_color(
        None,
        "RGBOwner"
    )
    assert dm_color["role"] == "member"

    controller = AppController.__new__(AppController)
    controller.view = TimerView()
    controller._rgb_timer_id = "timer-1"
    controller._rgb_active = True
    controller._cancel_rgb_cycler()
    assert controller.view.cancelled == ["timer-1"]
    assert controller._rgb_timer_id is None
    assert controller._rgb_active is False

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass

    print("=== WSZYSTKIE TESTY KOLOROWANYCH I RGB RÓL ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_colored_roles()
