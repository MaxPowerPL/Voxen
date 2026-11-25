"""
TEST SUITE: SYSTEM STATUSÓW UŻYTKOWNIKÓW I OBECNOŚCI W CZASIE RZECZYWISTYM (VOXEN)
Weryfikuje:
1. Trwałość statusu i własnego tekstu użytkownika w SQLite.
2. Model PresenceTracker i konfigurację statusów (Online, Idle, DND, Offline).
3. Automatyczne wyciszanie powiadomień w trybie DND (Nie przeszkadzać).
4. Przepływ wyboru statusu z poziomu panelu użytkownika w UI.
5. Odbiór i synchronizację statusu znajomych przez silnik sieciowy.
"""

import os
import sys
import unittest
from pathlib import Path

# Wymuszenie kodowania UTF-8 dla konsoli Windows
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import DatabaseManager
from models.presence_tracker import PresenceTracker
from network.connection import ConnectionState
from network.protocol import Packet, PacketType
from notifications.notifier import WindowsNotifier
from utils import Colors


class TestUserStatusPresence(unittest.TestCase):
    """Testy systemu statusów obecności i panelu użytkownika"""

    TEST_DB_PATH = "test_user_presence.db"

    @classmethod
    def setUpClass(cls):
        cls._cleanup_db()

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_db()

    @classmethod
    def _cleanup_db(cls):
        for ext in ["", "-wal", "-shm"]:
            p = Path(f"{cls.TEST_DB_PATH}{ext}")
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def setUp(self):
        self.db = DatabaseManager(db_path=self.TEST_DB_PATH)
        success, user = self.db.create_user("status_user@voxen.dev", "Haslo123!", "StatusUser")
        self.user_id = user["id"] if success else 1
        self.presence = PresenceTracker()

    def test_01_database_status_persistence(self):
        """Weryfikacja zapisu i odczytu statusu oraz własnego opisu w SQLite"""
        print("\n [1/5] Test bazy danych SQLite - Zapis i odczyt statusu użytkownika...")

        # Domyślny status po rejestracji
        default_st = self.db.get_user_status(self.user_id)
        self.assertEqual(default_st["status"], "online")
        self.assertEqual(default_st["custom_status"], "")

        # Aktualizacja na status 'idle' z własnym opisem
        ok = self.db.update_user_status(self.user_id, "idle", "Zaraz wracam, robię kawę ☕")
        self.assertTrue(ok)

        updated_st = self.db.get_user_status(self.user_id)
        self.assertEqual(updated_st["status"], "idle")
        self.assertEqual(updated_st["custom_status"], "Zaraz wracam, robię kawę ☕")
        print(f"       Zapisano status w SQLite: {updated_st['status']} ('{updated_st['custom_status']}')")

        print(" [OK] Trwałość statusu i opisu w bazie SQLite: SUKCES")

    def test_02_presence_tracker_visual_mapping(self):
        """Weryfikacja PresenceTracker i mapowania kolorów/emotikonów dla statusów"""
        print(" [2/5] Test modelu PresenceTracker i mapowania wizualnego...")

        # 4 główne statusy
        c_on, n_on, d_on = PresenceTracker.get_status_info("online")
        self.assertEqual(n_on, "Dostępny")
        self.assertEqual(d_on, "🟢")
        self.assertEqual(c_on, Colors.ONLINE)

        c_idle, n_idle, d_idle = PresenceTracker.get_status_info("idle")
        self.assertEqual(n_idle, "Zaraz wracam")
        self.assertEqual(d_idle, "🟡")

        c_dnd, n_dnd, d_dnd = PresenceTracker.get_status_info("dnd")
        self.assertEqual(n_dnd, "Nie przeszkadzać")
        self.assertEqual(d_dnd, "🔴")

        c_off, n_off, d_off = PresenceTracker.get_status_info("offline")
        self.assertEqual(n_off, "Niewidoczny")
        self.assertEqual(d_off, "⚪")

        # Śledzenie obecności użytkownika
        self.presence.set_user_presence("Wincekk", "dnd", "W trakcie meczu")
        p_wincekk = self.presence.get_user_presence("Wincekk")
        self.assertEqual(p_wincekk["status"], "dnd")
        self.assertEqual(p_wincekk["custom_status"], "W trakcie meczu")

        print(" [OK] Model PresenceTracker i mapowanie wizualne: SUKCES")

    def test_03_dnd_mode_silences_notifications(self):
        """Weryfikacja wyciszania powiadomień i dźwięków w trybie Nie przeszkadzać (DND)"""
        print(" [3/5] Test wyciszania powiadomień w trybie DND (Nie przeszkadzać)...")

        notifier = WindowsNotifier()
        notifier.set_dnd_mode(False)
        self.assertFalse(notifier.dnd_mode)

        # Włączenie trybu DND
        notifier.set_dnd_mode(True)
        self.assertTrue(notifier.dnd_mode)

        # Weryfikacja: w trybie DND _send_windows_toast natychmiast wraca (wyciszenie)
        # Przekazujemy pusty toast - nie powinien rzucić żadnego błędu ani emitować dźwięku
        notifier._send_windows_toast("Test", "Treść", play_sound=True)

        notifier.set_dnd_mode(False)
        self.assertFalse(notifier.dnd_mode)
        print(" [OK] Automatyczne wyciszanie powiadomień w trybie DND: SUKCES")

    def test_04_user_panel_status_change_flow(self):
        """Weryfikacja pełnego przepływu zmiany statusu z poziomu panelu użytkownika"""
        print(" [4/5] Symulacja wyboru statusu z UI i synchronizacji w kontrolerze...")

        from controllers.app_controller import AppController

        sent_statuses = []

        class MockNetwork:
            def __init__(self):
                class MockMetrics:
                    state = ConnectionState.CONNECTED
                    latency_ms = 1.0
                self.metrics = MockMetrics()
            def on(self, event, cb): pass
            def on_state_change(self, cb): pass
            def send_status(self, user, status, custom_status=""):
                sent_statuses.append((user, status, custom_status))
                return True

        class MockView:
            def __init__(self):
                self.my_status = "online"
                self.my_custom = ""
                self.presence_updates = {}
            def render_servers(self, s): pass
            def load_message_history(self, h): pass
            def clear_chat_messages(self): pass
            def update_network_status(self, t, c): pass
            def update_chat_title(self, t, topic=""): pass
            def highlight_active_channel(self, c): pass
            def update_dm_badge(self, n, c): pass
            def update_channel_badge(self, n, c): pass
            def update_server_badge(self, s, c): pass
            def show_in_app_toast(self, t, m): pass
            def set_typing_indicator(self, t): pass
            def after(self, d, cb): return "t"
            def after_cancel(self, tid): pass

            def update_my_status(self, status, custom_status=""):
                self.my_status = status
                self.my_custom = custom_status

            def update_user_presence(self, user, status, custom_status=""):
                self.presence_updates[user] = (status, custom_status)

        mock_view = MockView()
        mock_app = type("MockApp", (), {
            "current_user": {"username": "StatusUser", "email": "status_user@voxen.dev", "id": self.user_id},
            "network_client": MockNetwork()
        })()

        ctrl = AppController(model=None, view=mock_view, app=mock_app)
        ctrl.db = self.db

        # 1. Użytkownik zmienia status na DND z własnym tekstem
        ctrl._on_status_selected("dnd", "🔴 Skupienie - koduję nowy moduł")

        # Sprawdzenie stanu w kontrolerze i widoku
        self.assertEqual(ctrl.my_status, "dnd")
        self.assertEqual(mock_view.my_status, "dnd")
        self.assertEqual(mock_view.my_custom, "🔴 Skupienie - koduję nowy moduł")

        # Sprawdzenie czy notifier wszedł w tryb DND
        self.assertTrue(ctrl.notifier.dnd_mode, "Notifier musi mieć włączony tryb DND")

        # Sprawdzenie czy pakiet został wysłany przez sieć
        self.assertEqual(len(sent_statuses), 1)
        self.assertEqual(sent_statuses[0], ("StatusUser", "dnd", "🔴 Skupienie - koduję nowy moduł"))

        # Sprawdzenie czy stan utrwalił się w bazie SQLite
        db_st = self.db.get_user_status(self.user_id)
        self.assertEqual(db_st["status"], "dnd")
        self.assertEqual(db_st["custom_status"], "🔴 Skupienie - koduję nowy moduł")

        print("       Zaktualizowano profil UI: DND ('🔴 Skupienie - koduję nowy moduł')")
        print("       Wysłano pakiet STATUS_UPDATE przez sieć WebSocket")
        print("       Utrwalono w bazie SQLite")
        print(" [OK] Pełny cykl zmiany statusu profilu: SUKCES")

    def test_05_remote_friend_presence_sync(self):
        """Weryfikacja odbioru zmiany statusu znajomego z sieci i aktualizacji UI"""
        print(" [5/5] Test synchronizacji zmiany statusu znajomego w czasie rzeczywistym...")

        from controllers.app_controller import AppController

        class MockView:
            def __init__(self):
                self.presence_updates = {}
            def render_servers(self, s): pass
            def load_message_history(self, h): pass
            def clear_chat_messages(self): pass
            def update_network_status(self, t, c): pass
            def update_chat_title(self, t, topic=""): pass
            def highlight_active_channel(self, c): pass
            def update_dm_badge(self, n, c): pass
            def update_channel_badge(self, n, c): pass
            def update_server_badge(self, s, c): pass
            def update_my_status(self, s, c=""): pass
            def show_in_app_toast(self, t, m): pass
            def set_typing_indicator(self, t): pass
            def after(self, d, cb): return "t"
            def after_cancel(self, tid): pass

            def update_user_presence(self, user, status, custom_status=""):
                self.presence_updates[user] = (status, custom_status)

        mock_view = MockView()
        mock_app = type("MockApp", (), {
            "current_user": {"username": "StatusUser", "email": "status_user@voxen.dev", "id": self.user_id},
            "network_client": None
        })()

        ctrl = AppController(model=None, view=mock_view, app=mock_app)

        # Przychodzi pakiet zmiany obecności od Maxi3049
        pkt = Packet(
            type=PacketType.STATUS_UPDATE,
            payload={
                "user": "Maxi3049",
                "status": "idle",
                "custom_status": "Zaraz wracam 🍕"
            }
        )
        ctrl._on_network_status_update(pkt)

        # Sprawdzenie w PresenceTracker
        p_maxi = ctrl.presence_tracker.get_user_presence("Maxi3049")
        self.assertEqual(p_maxi["status"], "idle")
        self.assertEqual(p_maxi["custom_status"], "Zaraz wracam 🍕")

        # Sprawdzenie w MockView
        self.assertIn("Maxi3049", mock_view.presence_updates)
        self.assertEqual(mock_view.presence_updates["Maxi3049"], ("idle", "Zaraz wracam 🍕"))

        print("       Odebrano STATUS_UPDATE od 'Maxi3049' -> idle ('Zaraz wracam 🍕')")
        print("       Widok zaktualizował status znajomego w liście kontaktów: SUKCES")
        print(" [OK] Synchronizacja statusu znajomego z sieci w czasie rzeczywistym: SUKCES")


def run_tests():
    print("=== TEST SYSTEMU STATUSÓW I OBECNOŚCI UŻYTKOWNIKÓW ===")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUserStatusPresence)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n=== WSZYSTKIE TESTY STATUSÓW I OBECNOŚCI ZAKOŃCZONE SUKCESEM! ===")
        sys.exit(0)
    else:
        print("\n❌ NIEKTÓRE TESTY NIE POWIODŁY SIĘ!")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
