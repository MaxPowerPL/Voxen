"""
Główny punkt wejścia aplikacji Voxen
"""
import ctypes
import sys
import threading
import asyncio
import socket

import customtkinter as ctk

from utils import Config, Dimensions
from models.auth_model import AuthModel
from views.login_view import LoginView
from views.app_view import AppView
from controllers.login_controller import LoginController
from controllers.app_controller import AppController
from network import NetworkClient, ConnectionConfig, MockWebSocketServer


# === FIX DLA IKONY W PASKU ZADAŃ WINDOWS ===
if sys.platform == 'win32':
    myappid = 'voxen.messenger.app.v001'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
# ===========================================

# Konfiguracja motywu
ctk.set_appearance_mode(Config.APPEARANCE_MODE)
ctk.set_default_color_theme(Config.COLOR_THEME)


class App(ctk.CTk):
    """Główna aplikacja Voxen"""

    def __init__(self):
        super().__init__()

        # Konfiguracja okna
        self.title(Config.APP_TITLE)
        self.geometry(f"{Dimensions.WINDOW_WIDTH}x{Dimensions.WINDOW_HEIGHT}")
        self.minsize(Dimensions.WINDOW_WIDTH, Dimensions.WINDOW_HEIGHT)

        # Wyśrodkowanie okna
        self._center_window()

        # Ustaw ikonę
        try:
            self.iconbitmap("assets/images/logo.ico")
        except Exception as e:
            print(f"Nie można załadować ikony: {e}")

        # Konfiguracja grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Referencje do widoków i stanu
        self.current_view = None
        self.current_user = None
        self._mock_server = None

        # 1. Start wbudowanego serwera deweloperskiego (jeśli port wolny)
        self._start_local_mock_server_if_needed()

        # 2. Inicjalizacja asynchronicznego silnika sieciowego
        self.network_client = NetworkClient(
            config=ConnectionConfig(host="127.0.0.1", port=8765),
            ui_dispatcher=self._ui_dispatch
        )
        self.network_client.start()

        # Rejestracja czystego zamykania okna
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Inicjalizacja ekranu logowania
        self._setup_login_screen()

    def _ui_dispatch(self, callback, *args):
        """Bezpieczne przekazanie wywołania sieciowego do pętli zdarzeń Tkintera"""
        try:
            self.after(0, lambda: callback(*args))
        except Exception:
            pass

    def _start_local_mock_server_if_needed(self):
        """Uruchamia lokalny mock serwer deweloperski, jeśli żaden serwer nie nasłuchuje na porcie 8765"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", 8765))
        sock.close()

        if result != 0:
            def _run_server():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._mock_server = MockWebSocketServer(host="127.0.0.1", port=8765)
                loop.run_until_complete(self._mock_server.start())
                try:
                    loop.run_forever()
                except Exception:
                    pass

            server_thread = threading.Thread(
                target=_run_server,
                name="Voxen-DevServer",
                daemon=True
            )
            server_thread.start()
            print("🚀 Uruchomiono wbudowany silnik deweloperski Voxen MockServer (ws://127.0.0.1:8765)")

    def _center_window(self):
        """Wyśrodkowuje okno na ekranie przy starcie aplikacji z uwzględnieniem DPI"""
        self.update_idletasks()
        window_width = Dimensions.WINDOW_WIDTH
        window_height = Dimensions.WINDOW_HEIGHT

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))

        scale_factor = self._get_window_scaling()
        x = int(x * scale_factor)
        y = int(y * scale_factor)

        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def _setup_login_screen(self, allow_auto_login: bool = True):
        """Konfiguruje ekran logowania lub wznawia aktywną sesję (Auto-login)"""
        model = AuthModel("voxen.db")

        if allow_auto_login:
            saved_user = model.check_saved_session()
            if saved_user:
                print(f"🔑 Znaleziono aktywną sesję dla: {saved_user.get('email')}. Auto-logowanie...")
                self.show_main_app(saved_user)
                return

        login_view = LoginView(self)
        login_view.grid(row=0, column=0, sticky="nsew")

        controller = LoginController(model, login_view, self)
        login_view.set_controller(controller)

        self.current_view = login_view

    def show_login_screen(self):
        """Przełącza z powrotem do ekranu logowania (np. po wylogowaniu)"""
        if self.current_view:
            self.current_view.destroy()
            self.current_view = None
        self.current_user = None
        self._setup_login_screen(allow_auto_login=False)

    def show_main_app(self, user_data):
        """
        Przełącza z ekranu logowania do głównego ekranu aplikacji i autoryzuje sesję sieciową
        """
        self.current_user = user_data

        # Autentykacja w silniku sieciowym
        if self.network_client:
            self.network_client.authenticate(user_data.get("email", "User"))

        if self.current_view:
            self.current_view.destroy()

        app_view = AppView(self, user_data)
        app_controller = AppController(model=None, view=app_view, app=self)
        app_view.grid(row=0, column=0, sticky="nsew")
        app_view.set_controller(app_controller)

        self.current_view = app_view
        print(f"Przełączono do głównego ekranu. Aktywna sesja sieciowa: {user_data.get('email')}")

    def _on_window_close(self):
        """Zatrzymanie wątków i bezpieczne wyjście z aplikacji"""
        try:
            if hasattr(self, 'network_client') and self.network_client:
                self.network_client.stop()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
