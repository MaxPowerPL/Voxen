"""
TEST SUITE: WSKAŹNIK PISANIA W CZASIE RZECZYWISTYM DLA WIELU UŻYTKOWNIKÓW (VOXEN)
Weryfikuje:
1. Model TypingTracker i gramatyczne formatowanie w języku polskim (1, 2, 3 i 4+ użytkowników).
2. Izolację stanu pisania pomiędzy różnymi kanałami i rozmowami DM.
3. Mechanizm Auto-Decay (samoczynne przedawnienie przy braku pakietu stop).
4. Przetwarzanie zdarzeń sieciowych TYPING_START i TYPING_STOP w kontrolerze.
5. Throttling i debounce pisania lokalnego użytkownika.
6. Przełączanie aktywnej konwersacji i synchronizację UI.
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

from models.typing_tracker import TypingTracker
from network.connection import ConnectionState
from network.protocol import Packet, PacketType


class TestMultiUserTyping(unittest.TestCase):
    """Testy systemu wskaźnika pisania dla wielu użytkowników"""

    def setUp(self):
        self.tracker = TypingTracker(default_expiry=3.0)

    def test_01_polish_grammar_formatting(self):
        """Weryfikacja formatowania gramatycznego dla 1, 2, 3 i wielu osób"""
        print("\n [1/6] Test formatowania gramatycznego dla 1, 2, 3 i 4+ użytkowników...")

        conv = "Gaming#gry-pc"

        # 0 osób
        self.assertEqual(self.tracker.format_typing_text(conv), "")

        # 1 osoba
        self.tracker.user_started_typing(conv, "Wincekk")
        text_1 = self.tracker.format_typing_text(conv)
        self.assertEqual(text_1, "💬 Wincekk pisze...")
        print(f"       1 osoba: '{text_1}'")

        # 2 osoby
        self.tracker.user_started_typing(conv, "Maxi3049")
        text_2 = self.tracker.format_typing_text(conv)
        self.assertEqual(text_2, "💬 Maxi3049 i Wincekk piszą...")
        print(f"       2 osoby: '{text_2}'")

        # 3 osoby
        self.tracker.user_started_typing(conv, "Nemeczek")
        text_3 = self.tracker.format_typing_text(conv)
        self.assertEqual(text_3, "💬 Maxi3049, Nemeczek i Wincekk piszą...")
        print(f"       3 osoby: '{text_3}'")

        # 4 osoby
        self.tracker.user_started_typing(conv, "Kapi")
        text_4 = self.tracker.format_typing_text(conv)
        self.assertEqual(text_4, "💬 Kapi, Maxi3049 i 2 innych pisze...")
        print(f"       4 osoby: '{text_4}'")

        # Zakończenie pisania przez 2 osoby
        self.tracker.user_stopped_typing(conv, "Kapi")
        self.tracker.user_stopped_typing(conv, "Nemeczek")
        text_after = self.tracker.format_typing_text(conv)
        self.assertEqual(text_after, "💬 Maxi3049 i Wincekk piszą...")
        print(f"       Po zatrzymaniu: '{text_after}'")

        print(" [OK] Formatowanie gramatyczne w języku polskim: SUKCES")

    def test_02_conversation_and_channel_isolation(self):
        """Weryfikacja całkowitej izolacji wskaźników pisania pomiędzy kanałami i DM"""
        print(" [2/6] Test izolacji wskaźników pisania pomiędzy kanałami...")

        ch1 = "Gaming#gry-pc"
        ch2 = "Coding#python"
        dm = "Unity Bot"

        self.tracker.user_started_typing(ch1, "Wincekk")
        self.tracker.user_started_typing(ch2, "Nemeczek")
        self.tracker.user_started_typing(dm, "Unity Bot")

        self.assertEqual(self.tracker.get_typing_users(ch1), ["Wincekk"])
        self.assertEqual(self.tracker.get_typing_users(ch2), ["Nemeczek"])
        self.assertEqual(self.tracker.get_typing_users(dm), ["Unity Bot"])

        # Zatrzymanie w ch1 nie wpływa na ch2 i dm
        self.tracker.user_stopped_typing(ch1, "Wincekk")
        self.assertEqual(self.tracker.get_typing_users(ch1), [])
        self.assertEqual(self.tracker.get_typing_users(ch2), ["Nemeczek"])
        self.assertEqual(self.tracker.get_typing_users(dm), ["Unity Bot"])

        print(" [OK] Pełna izolacja kanałów i wiadomości prywatnych: SUKCES")

    def test_03_auto_decay_timeout(self):
        """Weryfikacja mechanizmu auto-decay (znikanie bez jawnego pakietu STOP)"""
        print(" [3/6] Test mechanizmu Auto-Decay (samoczynne przedawnienie)...")

        conv = "AutoDecayTest"
        short_tracker = TypingTracker(default_expiry=0.15)
        short_tracker.user_started_typing(conv, "ZapominalskiUser")

        # Zaraz po dodaniu użytkownik jest aktywny
        self.assertEqual(short_tracker.format_typing_text(conv), "💬 ZapominalskiUser pisze...")

        # Czekamy na przekroczenie czasu ważności
        time.sleep(0.2)
        changed = short_tracker.clean_expired()
        self.assertTrue(changed, "clean_expired powinien zgłosić zmianę")
        self.assertEqual(short_tracker.format_typing_text(conv), "", "Wskaźnik powinien samoczynnie zniknąć")

        print(" [OK] Mechanizm Auto-Decay po przekroczeniu limitu czasu: SUKCES")

    def test_04_controller_multi_user_typing_events(self):
        """Test obsługi przychodzących pakietów sieciowych TYPING_START/STOP w kontrolerze"""
        print(" [4/6] Symulacja przychodzących pakietów TYPING_START/STOP w kontrolerze...")

        from controllers.app_controller import AppController

        class MockView:
            def __init__(self):
                self.typing_text = ""
            def render_servers(self, s): pass
            def load_message_history(self, h): pass
            def clear_chat_messages(self): pass
            def add_message(self, **kwargs): pass
            def update_network_status(self, text, color): pass
            def update_chat_title(self, text, topic=""): pass
            def highlight_active_channel(self, ch): pass
            def show_dms_sidebar(self): pass
            def show_server_channels(self, sid, sname, chs): pass
            def update_dm_badge(self, name, count): pass
            def update_channel_badge(self, cname, count): pass
            def update_server_badge(self, sid, count): pass
            def update_my_status(self, status, custom_status=""): pass
            def update_user_presence(self, user, status, custom_status=""): pass
            def show_in_app_toast(self, t, m): pass
            def clear_message_input(self): pass
            def set_typing_indicator(self, text):
                self.typing_text = text
            def after(self, delay, callback):
                # Nie wywołujemy w nieskończoność w testach synchronicznych
                return "after_id"
            def after_cancel(self, timer_id): pass

        class MockApp:
            def __init__(self):
                self.current_user = {"username": "LocalArchitect", "email": "me@voxen.dev"}
                self.network_client = None

        mock_view = MockView()
        mock_app = MockApp()

        ctrl = AppController(model=None, view=mock_view, app=mock_app)
        ctrl.current_conversation = "Gaming#gry-pc"
        ctrl.current_channel = "gry-pc"
        ctrl.current_server = "Gaming"

        # 1. Przychodzi pakiet TYPING_START od Wincekk
        pkt1 = Packet(
            type=PacketType.TYPING_START,
            payload={"user": "Wincekk", "target": "Gaming#gry-pc"}
        )
        ctrl._on_network_typing_start(pkt1)
        self.assertEqual(mock_view.typing_text, "💬 Wincekk pisze...")

        # 2. Przychodzi pakiet TYPING_START od Maxi3049
        pkt2 = Packet(
            type=PacketType.TYPING_START,
            payload={"user": "Maxi3049", "target": "Gaming#gry-pc"}
        )
        ctrl._on_network_typing_start(pkt2)
        self.assertEqual(mock_view.typing_text, "💬 Maxi3049 i Wincekk piszą...")

        # 3. Własny pakiet pisania (LocalArchitect) jest ignorowany
        pkt_self = Packet(
            type=PacketType.TYPING_START,
            payload={"user": "LocalArchitect", "target": "Gaming#gry-pc"}
        )
        ctrl._on_network_typing_start(pkt_self)
        self.assertEqual(mock_view.typing_text, "💬 Maxi3049 i Wincekk piszą...")

        # 4. Wincekk wysyła TYPING_STOP
        pkt1_stop = Packet(
            type=PacketType.TYPING_STOP,
            payload={"user": "Wincekk", "target": "Gaming#gry-pc"}
        )
        ctrl._on_network_typing_stop(pkt1_stop)
        self.assertEqual(mock_view.typing_text, "💬 Maxi3049 pisze...")

        # 5. Maxi3049 wysyła TYPING_STOP
        pkt2_stop = Packet(
            type=PacketType.TYPING_STOP,
            payload={"user": "Maxi3049", "target": "Gaming#gry-pc"}
        )
        ctrl._on_network_typing_stop(pkt2_stop)
        self.assertEqual(mock_view.typing_text, "")

        print(" [OK] Przetwarzanie zdarzeń sieciowych i aktualizacja UI w kontrolerze: SUKCES")

    def test_05_local_user_typing_throttling_and_debounce(self):
        """Weryfikacja throttlingu i automatycznego zakończenia pisania przy wysłaniu wiadomości"""
        print(" [5/6] Test throttlingu pisania lokalnego użytkownika i debounce...")

        from controllers.app_controller import AppController

        sent_packets = []

        class MockMetrics:
            state = ConnectionState.CONNECTED
            latency_ms = 1.0

        class MockNetwork:
            def __init__(self):
                self.metrics = MockMetrics()
            def on(self, event, callback): pass
            def on_state_change(self, callback): pass
            def send_typing(self, user, target, is_typing):
                sent_packets.append((user, target, is_typing))
                return True
            def send_message(self, target, content, sender, is_dm):
                return True

        class MockView:
            def render_servers(self, s): pass
            def load_message_history(self, h): pass
            def clear_chat_messages(self): pass
            def add_message(self, **kwargs): pass
            def update_network_status(self, text, color): pass
            def update_chat_title(self, text, topic=""): pass
            def highlight_active_channel(self, ch): pass
            def show_dms_sidebar(self): pass
            def show_server_channels(self, sid, sname, chs): pass
            def update_dm_badge(self, name, count): pass
            def update_channel_badge(self, cname, count): pass
            def update_server_badge(self, sid, count): pass
            def update_my_status(self, status, custom_status=""): pass
            def update_user_presence(self, user, status, custom_status=""): pass
            def show_in_app_toast(self, t, m): pass
            def clear_message_input(self): pass
            def set_typing_indicator(self, text): pass
            def after(self, delay, callback): return "timer_123"
            def after_cancel(self, timer_id): pass

        class MockApp:
            def __init__(self):
                self.current_user = {"username": "LocalArchitect", "email": "me@voxen.dev"}
                self.network_client = MockNetwork()

        ctrl = AppController(model=None, view=MockView(), app=MockApp())
        ctrl.current_conversation = "Unity Bot"

        # 1. Pierwsze wciśnięcie klawisza -> wysyła pakiet TYPING START
        ctrl.handle_user_typing()
        self.assertEqual(len(sent_packets), 1)
        self.assertEqual(sent_packets[0], ("LocalArchitect", "Unity Bot", True))

        # 2. Kolejne szybkie wciśnięcia klawiszy -> throttled (brak powtórnego pakietu)
        ctrl.handle_user_typing()
        ctrl.handle_user_typing()
        self.assertEqual(len(sent_packets), 1, "Kolejne wciśnięcia w oknie throttlingu nie mogą zalewać sieci")

        # 3. Wysłanie wiadomości (Enter) -> natychmiast wysyła TYPING STOP
        ctrl.handle_send_message("Cześć!")
        self.assertEqual(len(sent_packets), 2)
        self.assertEqual(sent_packets[1], ("LocalArchitect", "Unity Bot", False))

        print(" [OK] Throttling i natychmiastowe zwalnianie pisania przy Enter: SUKCES")

    def test_06_channel_switch_indicator_sync(self):
        """Weryfikacja prawidłowej synchronizacji wskaźnika pisania przy przełączaniu kanałów"""
        print(" [6/6] Test synchronizacji wskaźnika przy przełączaniu kanałów...")

        from controllers.app_controller import AppController

        class MockView:
            def __init__(self):
                self.typing_text = ""
            def render_servers(self, s): pass
            def load_message_history(self, h): pass
            def clear_chat_messages(self): pass
            def add_message(self, **kwargs): pass
            def update_network_status(self, text, color): pass
            def update_chat_title(self, text, topic=""): pass
            def highlight_active_channel(self, ch): pass
            def show_dms_sidebar(self): pass
            def show_server_channels(self, sid, sname, chs): pass
            def update_dm_badge(self, name, count): pass
            def update_channel_badge(self, cname, count): pass
            def update_server_badge(self, sid, count): pass
            def update_my_status(self, status, custom_status=""): pass
            def update_user_presence(self, user, status, custom_status=""): pass
            def show_in_app_toast(self, t, m): pass
            def clear_message_input(self): pass
            def set_typing_indicator(self, text):
                self.typing_text = text
            def after(self, delay, callback): return "timer"
            def after_cancel(self, timer_id): pass

        class MockApp:
            def __init__(self):
                self.current_user = {"username": "LocalArchitect", "email": "me@voxen.dev"}
                self.network_client = None

        mock_view = MockView()
        ctrl = AppController(model=None, view=mock_view, app=MockApp())

        # Zarejestruj piszących na dwóch różnych kanałach
        ctrl.typing_tracker.user_started_typing("Gaming#gry-pc", "Gamer1")
        ctrl.typing_tracker.user_started_typing("Coding#python", "Coder1")

        # Przełącz na Gaming#gry-pc
        ctrl.current_server = "Gaming"
        ctrl.handle_channel_click(server_id=2, channel_name="gry-pc")
        self.assertEqual(mock_view.typing_text, "💬 Gamer1 pisze...")

        # Przełącz na Coding#python
        ctrl.current_server = "Coding"
        ctrl.handle_channel_click(server_id=3, channel_name="python")
        self.assertEqual(mock_view.typing_text, "💬 Coder1 pisze...")

        # Przełącz na Direct Messages Unity Bot (gdzie nikt nie pisze)
        ctrl.handle_conversation_click("Unity Bot")
        self.assertEqual(mock_view.typing_text, "")

        print(" [OK] Prawidłowe przywracanie stanu pisania przy przełączaniu kanałów: SUKCES")


def run_tests():
    print("=== TEST WSKAŹNIKA PISANIA W CZASIE RZECZYWISTYM (MULTI-USER) ===")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMultiUserTyping)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n=== WSZYSTKIE TESTY WSKAŹNIKA PISANIA ZAKOŃCZONE SUKCESEM! ===")
        sys.exit(0)
    else:
        print("\n❌ NIEKTÓRE TESTY NIE POWIODŁY SIĘ!")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
