"""
Główny punkt wejścia aplikacji
"""
import customtkinter as ctk
from utils import Config, Dimensions
from models.auth_model import AuthModel
from views.login_view import LoginView
from views.app_view import AppView
from controllers.login_controller import LoginController

# === FIX DLA IKONY W PASKU ZADAŃ WINDOWS ===
import ctypes
import sys

# Ustaw AppUserModelID PRZED utworzeniem okna
if sys.platform == 'win32':
    myappid = 'voxen.messenger.app.v001'  # Unikalny ID aplikacji
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
# ===========================================

# Konfiguracja motywu
ctk.set_appearance_mode(Config.APPEARANCE_MODE)
ctk.set_default_color_theme(Config.COLOR_THEME)


class App(ctk.CTk):
    """Główna aplikacja"""

    def __init__(self):
        super().__init__()

        # Konfiguracja okna
        self.title(Config.APP_TITLE)
        self.geometry(f"{Dimensions.WINDOW_WIDTH}x{Dimensions.WINDOW_HEIGHT}")
        self.minsize(Dimensions.WINDOW_WIDTH, Dimensions.WINDOW_HEIGHT)

        # === WYŚRODKUJ OKNO NA STARCIE ===
        self._center_window()
        # =================================

        # Ustaw ikonę
        try:
            self.iconbitmap("assets/images/logo.ico")
        except Exception as e:
            print(f"Nie można załadować ikony: {e}")
        # ===============================================

        # Konfiguracja grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Referencje do widoków
        self.current_view = None
        self.current_user = None

        # Inicjalizacja ekranu logowania
        self._setup_login_screen()

    def _center_window(self):
        """
        Wyśrodkowuje okno na ekranie przy starcie aplikacji.
        Działa z CustomTkinter uwzględniając skalowanie DPI (125%, 150% itd.)
        """
        # Zaktualizuj okno aby uzyskać prawdziwe wymiary
        self.update_idletasks()

        # Pobierz rozmiar okna
        window_width = Dimensions.WINDOW_WIDTH
        window_height = Dimensions.WINDOW_HEIGHT

        # Pobierz rozmiar ekranu
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Oblicz pozycję x, y dla centrum ekranu
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))

        # Uwzględnij skalowanie DPI dla CustomTkinter
        scale_factor = self._get_window_scaling()
        x = int(x * scale_factor)
        y = int(y * scale_factor)

        # Ustaw geometrię okna z pozycją
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def _setup_login_screen(self):
        """Konfiguruje ekran logowania według wzorca MVC"""
        # Model
        model = AuthModel("users.json")

        # View
        login_view = LoginView(self)
        login_view.grid(row=0, column=0, sticky="nsew")

        # Controller
        controller = LoginController(model, login_view, self)

        # Połącz View z Controller
        login_view.set_controller(controller)

        # Zapisz referencję do obecnego widoku
        self.current_view = login_view

    def show_main_app(self, user_data):
        """
        Przełącza z ekranu logowania do głównego ekranu aplikacji

        Args:
            user_data: Dane zalogowanego użytkownika
        """
        # Zapisz dane użytkownika
        self.current_user = user_data

        # Usuń stary widok (ekran logowania)
        if self.current_view:
            self.current_view.destroy()

        # Utwórz nowy widok (główny ekran)
        app_view = AppView(self, user_data)
        app_view.grid(row=0, column=0, sticky="nsew")

        # Zaktualizuj referencję do obecnego widoku
        self.current_view = app_view

        print("Przełączono do głównego ekranu aplikacji")


if __name__ == "__main__":
    app = App()
    app.mainloop()
