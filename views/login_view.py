"""
VIEW - Ekran logowania
"""
import customtkinter as ctk
from utils import Colors, Fonts, Dimensions


class LoginView(ctk.CTkFrame):
    """Widok ekranu logowania (View w MVC)"""

    def __init__(self, parent):
        """
        Inicjalizacja widoku logowania

        Args:
            parent: Rodzic (główne okno aplikacji)
        """
        super().__init__(parent, fg_color="transparent")

        self.controller = None

        # Konfiguracja grid dla podziału 50/50
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Utwórz interfejs
        self._create_widgets()

    def _create_widgets(self):
        """Tworzy widgety ekranu logowania"""
        self._create_left_panel()
        self._create_right_panel()

    def _create_left_panel(self):
        """Tworzy lewą stronę - tło graficzne z dynamicznym skalowaniem"""
        # Utwórz frame
        self.left_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_LEFT,
            corner_radius=0
        )
        self.left_frame.grid(row=0, column=0, sticky="nsew")

        # Label dla obrazka
        self.bg_label = ctk.CTkLabel(
            self.left_frame,
            text=""
        )
        self.bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Załaduj obrazek tła
        try:
            from PIL import Image, ImageOps
            self.original_bg_image = Image.open("assets/images/login_background.png")

            # Pierwsza kalkulacja rozmiaru
            self._update_background_size(None)

            # Binduj funkcję do zmiany rozmiaru frame'a
            self.left_frame.bind('<Configure>', self._update_background_size)

        except FileNotFoundError:
            self.bg_label.configure(
                text="Voxen",
                font=("Segoe UI", 48, "bold"),
                text_color=Colors.TEXT_PRIMARY
            )
            print("Ostrzeżenie: Nie znaleziono pliku login_background.png")
        except ImportError:
            print("Ostrzeżenie: Brak biblioteki PIL/Pillow")

    def _update_background_size(self, event):
        """Dynamicznie zmienia rozmiar obrazka tła (CSS background-size: cover)"""
        try:
            from PIL import Image, ImageOps

            if event:
                new_width = event.width
                new_height = event.height
            else:
                self.left_frame.update_idletasks()
                new_width = self.left_frame.winfo_width()
                new_height = self.left_frame.winfo_height()

            if new_width <= 1 or new_height <= 1:
                return

            resized_image = ImageOps.fit(
                self.original_bg_image,
                (new_width, new_height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )

            self.bg_photo = ctk.CTkImage(
                light_image=resized_image,
                dark_image=resized_image,
                size=(new_width, new_height)
            )

            self.bg_label.configure(image=self.bg_photo)

        except Exception as e:
            print(f"Błąd podczas skalowania obrazka: {e}")

    def _create_right_panel(self):
        """Tworzy prawą stronę - formularz logowania"""
        self.right_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_RIGHT,
            corner_radius=0
        )
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        # Formularz logowania
        self._create_login_form()

    def _create_login_form(self):
        """Tworzy formularz logowania"""
        # Kontener wyśrodkowany
        login_container = ctk.CTkFrame(
            self.right_frame,
            fg_color="transparent"
        )
        login_container.place(relx=0.5, rely=0.5, anchor="center")

        # Tytuł
        title = ctk.CTkLabel(
            login_container,
            text="Witamy ponownie!",
            font=Fonts.TITLE,
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(pady=(0, 8))

        # Subtitle
        subtitle = ctk.CTkLabel(
            login_container,
            text="Cieszymy się, że znów z nami jesteś!",
            font=Fonts.SUBTITLE,
            text_color=Colors.TEXT_SECONDARY
        )
        subtitle.pack(pady=(0, 25))

        # Kontener dla ikony + tekstu
        email_label_container = ctk.CTkFrame(
            login_container,
            fg_color="transparent"
        )
        email_label_container.pack(fill="x", padx=2)

        # Ikona
        email_icon = ctk.CTkLabel(
            email_label_container,
            text="📧",
            font=("Segoe UI", 14),
            text_color=Colors.ICON_COLOR,  # Pomarańczowy
            anchor="w"
        )
        email_icon.pack(side="left", padx=(0, 5))

        # Tekst
        email_text = ctk.CTkLabel(
            email_label_container,
            text="Email:",
            font=Fonts.LABEL,
            text_color=Colors.TEXT_LABEL,
            anchor="w"
        )
        email_text.pack(side="left")

        self.email_entry = ctk.CTkEntry(
            login_container,
            width=320,
            height=45,
            font=Fonts.INPUT,
            fg_color=Colors.INPUT_BG,
            border_color=Colors.INPUT_BORDER,
            border_width=2,
            text_color=Colors.TEXT_INPUT,
            placeholder_text="podaj@email.com"
        )
        self.email_entry.pack(pady=(5, 15))


        # Kontener dla ikony + tekstu
        password_label_container = ctk.CTkFrame(
            login_container,
            fg_color="transparent"
        )
        password_label_container.pack(fill="x", padx=2)

        # Ikona
        password_icon = ctk.CTkLabel(
            password_label_container,
            text="🔐",
            font=("Segoe UI", 14),
            text_color=Colors.ICON_COLOR,
            anchor="w"
        )
        password_icon.pack(side="left", padx=(0, 5))

        # Tekst
        password_text = ctk.CTkLabel(
            password_label_container,
            text="Hasło:",
            font=Fonts.LABEL,
            text_color=Colors.TEXT_LABEL,
            anchor="w"
        )
        password_text.pack(side="left")

        self.password_entry = ctk.CTkEntry(
            login_container,
            width=320,
            height=45,
            font=Fonts.INPUT,
            fg_color=Colors.INPUT_BG,
            border_color=Colors.INPUT_BORDER,
            border_width=2,
            text_color=Colors.TEXT_INPUT,
            placeholder_text="••••••••",
            show="•"
        )
        self.password_entry.pack(pady=(5, 20))

        # Przycisk
        self.login_button = ctk.CTkButton(
            login_container,
            text="Zaloguj się",
            width=320,
            height=45,
            font=Fonts.BUTTON,
            fg_color=Colors.BUTTON_PRIMARY,
            hover_color=Colors.BUTTON_PRIMARY_HOVER,
            command=self._on_login_click
        )
        self.login_button.pack()

        # Komunikat błędu
        self.error_label = ctk.CTkLabel(
            login_container,
            text="",
            font=Fonts.MESSAGE,
            text_color=Colors.ERROR
        )
        self.error_label.pack(pady=(15, 0))

    def _on_login_click(self):
        """Deleguje logowanie do controllera"""
        if self.controller:
            self.controller.handle_login()

    def setup_key_bindings(self):
        """
        Konfiguruje skróty klawiszowe.
        Wywoływana PRZEZ set_controller() gdy controller jest już ustawiony.
        """
        # Sprawdź czy widgety istnieją (defensive programming)
        if not hasattr(self, 'email_entry') or not hasattr(self, 'password_entry'):
            print("⚠️ Ostrzeżenie: Próba ustawienia bindingów przed utworzeniem widgetów!")
            return

        # Enter w polu email → fokus na hasło
        self.email_entry.bind('<Return>', self._on_email_enter)

        # Enter w polu hasło → wywołaj logowanie
        self.password_entry.bind('<Return>', self._on_password_enter)

    def _on_email_enter(self, event):
        """Enter w email → fokus na hasło"""
        self.password_entry.focus()

    def _on_password_enter(self, event):
        """Enter w hasło → deleguj do controllera"""
        if self.controller:
            self.controller.handle_login()

    def set_controller(self, controller):
        """
        Ustawia controller i konfiguruje bindingi.

        Args:
            controller: Instancja LoginController
        """
        self.controller = controller
        # ✅ Teraz widgety już istnieją, więc można ustawić bindingi
        self.setup_key_bindings()

    def get_credentials(self):
        """
        Pobiera dane logowania z formularza.

        Returns:
            tuple: (email, password)
        """
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        return email, password

    def show_error(self, message):
        """
        Wyświetla komunikat o błędzie.

        Args:
            message: Treść komunikatu
        """
        self.error_label.configure(text=message)

    def clear_error(self):
        """Czyści komunikat o błędzie"""
        self.error_label.configure(text="")
