"""
TEST SUITE: SYSTEM POWIADOMIEŃ I ODZNAK NIEPRZECZYTANYCH WIADOMOŚCI (VOXEN)
Weryfikuje:
1. Trwałość statusu is_read w SQLite WAL.
2. Zliczanie nieprzeczytanych wiadomości dla DMs, kanałów i agregację dla serwerów.
3. Działanie modułu WindowsNotifier (Singleton, in-app listeners, toast worker).
4. Automatyczne odznaki (Unread Badges) i ich czyszczenie przy otwarciu konwersacji.
5. Prawidłową izolację i brak regresji.
"""

import os
import sys
import time
import unittest
from pathlib import Path

# Wymuszenie kodowania UTF-8 dla konsoli Windows
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import DatabaseManager
from models.chat_model import ChatModel
from models.server_model import ServerModel
from notifications.notifier import WindowsNotifier
from network.protocol import Packet, PacketType


class TestNotificationsAndBadges(unittest.TestCase):
    """Kompleksowe testy systemu powiadomień i odznak nieprzeczytanych wiadomości"""

    TEST_DB_PATH = "test_notifications_badges.db"

    @classmethod
    def setUpClass(cls):
        # Usuń bazę testową jeśli została z poprzednich testów
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
        self.chat_model = ChatModel(db=self.db)
        self.server_model = ServerModel(db=self.db)
        self.user = "TestArchitect"

    def test_01_database_unread_flag_and_counts(self):
        """Weryfikacja flagi is_read i zliczania nieprzeczytanych wiadomości w SQLite"""
        print("\n [1/5] Test bazy danych SQLite i statusów odczytania (is_read)...")

        # 1. Zapis wiadomości przeczytanej (np. wysłanej przez samego użytkownika)
        self.chat_model.save_message(
            sender=self.user,
            target="Unity Bot",
            content="Moja własna wiadomość",
            is_dm=True,
            is_read=True
        )

        # 2. Zapis 3 nieprzeczytanych wiadomości od bota
        for i in range(3):
            self.chat_model.save_message(
                sender="Unity Bot",
                target=self.user,
                content=f"Wiadomość #{i+1}",
                is_dm=True,
                is_read=False
            )

        # 3. Zapis 2 nieprzeczytanych wiadomości na kanale serwera
        for i in range(2):
            self.chat_model.save_message(
                sender="Wincekk",
                target="Gaming#gry-pc",
                content=f"Hej, gramy w coś? #{i+1}",
                is_dm=False,
                is_read=False
            )

        # Weryfikacja liczników
        dm_unread = self.chat_model.get_unread_count("Unity Bot", self.user)
        self.assertEqual(dm_unread, 3, "Licznik nieprzeczytanych wiadomości DM powinien wynosić 3")

        ch_unread = self.chat_model.get_unread_count("Gaming#gry-pc", self.user)
        self.assertEqual(ch_unread, 2, "Licznik nieprzeczytanych wiadomości kanału powinien wynosić 2")

        # Pobranie pełnego podsumowania (mapy nieprzeczytanych)
        summary = self.chat_model.get_all_unread_counts(self.user)
        self.assertEqual(summary.get("Unity Bot"), 3)
        self.assertEqual(summary.get("Gaming#gry-pc"), 2)
        print(f"       Załadowano liczniki: DM (Unity Bot: {dm_unread}), Kanał (Gaming#gry-pc: {ch_unread})")
        print(" [OK] Flaga is_read i liczniki nieprzeczytanych w SQLite: SUKCES")

    def test_02_mark_as_read_isolation(self):
        """Weryfikacja oznaczania wiadomości jako przeczytane (mark_as_read)"""
        print(" [2/5] Test oznaczania konwersacji jako przeczytana (mark_as_read)...")

        # Oznacz DM Unity Bot jako przeczytane
        updated_dms = self.chat_model.mark_as_read("Unity Bot", self.user)
        self.assertEqual(updated_dms, 3, "Powinno zaktualizować dokładnie 3 wiadomości")

        # Sprawdź stan po oznaczeniu
        dm_unread_after = self.chat_model.get_unread_count("Unity Bot", self.user)
        self.assertEqual(dm_unread_after, 0, "Licznik DM po przeczytaniu powinien wynosić 0")

        # Upewnij się, że kanał Gaming#gry-pc nadal ma 2 nieprzeczytane (izolacja)
        ch_unread_after = self.chat_model.get_unread_count("Gaming#gry-pc", self.user)
        self.assertEqual(ch_unread_after, 2, "Izolacja: kanał serwera nadal powinien mieć 2 nieprzeczytane")

        # Oznacz kanał jako przeczytany
        updated_ch = self.chat_model.mark_as_read("Gaming#gry-pc", self.user)
        self.assertEqual(updated_ch, 2)
        self.assertEqual(self.chat_model.get_unread_count("Gaming#gry-pc", self.user), 0)

        print(" [OK] Precyzyjne oznaczanie jako przeczytane i izolacja: SUKCES")

    def test_03_windows_notifier_module(self):
        """Test działania modułu WindowsNotifier (Singleton, listeners, asynchroniczny toast)"""
        print(" [3/5] Test modułu WindowsNotifier (Singleton i in-app listeners)...")

        n1 = WindowsNotifier()
        n2 = WindowsNotifier()
        self.assertIs(n1, n2, "WindowsNotifier musi być Singletonem")

        received_events = []

        def _test_listener(title, msg):
            received_events.append((title, msg))

        n1.add_listener(_test_listener)

        # Wyślij testowe powiadomienie bez dźwięku
        n1.notify(title="Voxen Test", message="Testowa notyfikacja", play_sound=False)

        # Sprawdź czy in-app listener odebrał powiadomienie
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0][0], "Voxen Test")
        self.assertEqual(received_events[0][1], "Testowa notyfikacja")

        # Posprzątaj listener
        n1.remove_listener(_test_listener)
        print(" [OK] Moduł WindowsNotifier i in-app dispatch: SUKCES")

    def test_04_controller_badge_and_notification_flow(self):
        """Test pełnego przepływu: nadejście wiadomości sieciowej w tle -> Badge + Notyfikacja"""
        print(" [4/5] Symulacja nadejścia wiadomości w tle i odznak (Unread Badges)...")

        from controllers.app_controller import AppController

        # Mock widoku
        class MockAppView:
            def __init__(self):
                self.dm_badges = {}
                self.channel_badges = {}
                self.server_badges = {}
                self.toasts = []

            def render_servers(self, s): pass
            def load_message_history(self, h): pass
            def clear_chat_messages(self): pass
            def add_message(self, **kwargs): pass
            def set_typing_indicator(self, text): pass
            def update_network_status(self, text, color): pass
            def update_chat_title(self, text, topic=""): pass
            def highlight_active_channel(self, ch): pass
            def show_dms_sidebar(self): pass
            def show_server_channels(self, sid, sname, chs): pass
            def show_create_server_modal(self, cb): pass
            def show_create_channel_modal(self, sname, cb): pass
            def clear_message_input(self): pass

            def update_dm_badge(self, name, count):
                self.dm_badges[name] = count

            def update_channel_badge(self, channel_name, count):
                self.channel_badges[channel_name] = count

            def update_server_badge(self, server_id, count):
                self.server_badges[server_id] = count

            def show_in_app_toast(self, title, message, duration_ms=4000):
                self.toasts.append((title, message))

            def after(self, delay, callback):
                # Natychmiastowe wykonanie dla celów testowych
                try:
                    callback()
                except Exception:
                    pass

        class MockApp:
            def __init__(self):
                self.current_user = {"username": "TestArchitect", "email": "test@voxen.dev", "id": 1}
                self.network_client = None

        mock_view = MockAppView()
        mock_app = MockApp()

        ctrl = AppController(model=None, view=mock_view, app=mock_app)
        ctrl.chat_model = self.chat_model
        ctrl.server_model = self.server_model

        # Użytkownik ma aktywną rozmowę z 'Unity Bot'
        ctrl.current_conversation = "Unity Bot"
        ctrl.current_channel = None

        # 1. Przychodzi wiadomość od 'Kapi' (konwersacja NIEAKTYWNA w tle)
        pkt_kapi = Packet(
            type=PacketType.MESSAGE_RECV,
            payload={
                "sender": "Kapi",
                "target": "TestArchitect",
                "content": "Hej, widziałeś nowy silnik?",
                "is_dm": True
            }
        )
        ctrl._on_network_message(pkt_kapi)

        # Sprawdzenie czy odznaka dla Kapi wynosi 1
        self.assertEqual(mock_view.dm_badges.get("Kapi"), 1, "Badge dla Kapi powinien wynosić 1")

        # Sprawdzenie czy ikona DMs (None) w lewej kolumnie pokazuje 1
        self.assertEqual(mock_view.server_badges.get(None), 1, "Suma nieprzeczytanych DMs powinna wynosić 1")

        # Sprawdzenie czy wysłano powiadomienie toast
        self.assertTrue(any("Kapi" in t[0] for t in mock_view.toasts), "Powinien pojawić się toast z Kapi")

        print("       Odznaka DM 'Kapi': 1, Odznaka lewej kolumny DMs: 1")
        print("       Wygenerowano toast: Voxen • Kapi")

        # 2. Kliknięcie w konwersację z 'Kapi' -> wyczyszczenie odznaki
        ctrl.handle_conversation_click("Kapi")
        self.assertEqual(mock_view.dm_badges.get("Kapi"), 0, "Badge dla Kapi po kliknięciu powinien zniknąć (0)")
        self.assertEqual(mock_view.server_badges.get(None), 0, "Suma DMs po kliknięciu powinna wynosić 0")

        print(" [OK] Automatyczna aktualizacja odznak i czyszczenie po otwarciu: SUKCES")

    def test_05_server_channel_unread_and_aggregation(self):
        """Weryfikacja agregacji nieprzeczytanych wiadomości serwera z wielu kanałów"""
        print(" [5/5] Test agregacji nieprzeczytanych wiadomości serwerów z wielu kanałów...")

        servers = self.server_model.get_all_servers()
        gaming_server = next((s for s in servers if s["name"] == "Gaming"), None)
        self.assertIsNotNone(gaming_server, "Serwer Gaming musi istnieć w bazie")

        gaming_id = gaming_server["id"]

        # Zapisz 2 nieprzeczytane na kanale #gry-pc i 1 na #konsole
        self.chat_model.save_message("Chaos", "Gaming#gry-pc", "Gra ktoś?", is_dm=False, is_read=False)
        self.chat_model.save_message("Nemeczek", "Gaming#gry-pc", "Ja mogę!", is_dm=False, is_read=False)
        self.chat_model.save_message("Maxi3049", "Gaming#konsole", "PS5 update gotowy", is_dm=False, is_read=False)

        summary = self.chat_model.get_all_unread_counts(self.user)
        self.assertEqual(summary.get("Gaming#gry-pc"), 2)
        self.assertEqual(summary.get("Gaming#konsole"), 1)

        # Łączna liczba dla serwera Gaming: 2 + 1 = 3
        channels = self.server_model.get_channels(gaming_id)
        total_gaming_unread = sum(summary.get(f"Gaming#{ch['name']}", 0) for ch in channels)
        self.assertEqual(total_gaming_unread, 3, "Łączna liczba nieprzeczytanych serwera Gaming powinna wynosić 3")

        print(f"       Kanał #gry-pc: 2, Kanał #konsole: 1 -> Łącznie serwer Gaming: {total_gaming_unread}")

        # Oznaczenie #gry-pc jako przeczytany
        self.chat_model.mark_as_read("Gaming#gry-pc", self.user)
        summary_after = self.chat_model.get_all_unread_counts(self.user)
        self.assertEqual(summary_after.get("Gaming#gry-pc", 0), 0)
        self.assertEqual(summary_after.get("Gaming#konsole"), 1)

        total_gaming_after = sum(summary_after.get(f"Gaming#{ch['name']}", 0) for ch in channels)
        self.assertEqual(total_gaming_after, 1, "Po przeczytaniu #gry-pc serwer Gaming powinien mieć 1 nieprzeczytaną")

        print(" [OK] Agregacja nieprzeczytanych kanałów na serwerze: SUKCES")


def run_tests():
    print("=== TEST SYSTEMU POWIADOMIEŃ I ODZNAK NIEPRZECZYTANYCH WIADOMOŚCI ===")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNotificationsAndBadges)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n=== WSZYSTKIE TESTY POWIADOMIEŃ I ODZNAK ZAKOŃCZONE SUKCESEM! ===")
        sys.exit(0)
    else:
        print("\n❌ NIEKTÓRE TESTY NIE POWIODŁY SIĘ!")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
