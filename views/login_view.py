"""
VIEW - Ekran logowania i rejestracji (MVC View)
"""

import customtkinter as ctk
from utils import Colors, Fonts, Dimensions


class LoginView(ctk.CTkFrame):
    """Widok ekranu logowania i rejestracji (View w MVC)"""

    MODE_LOGIN = "login"
    MODE_REGISTER = "register"

    def __init__(self, parent):
        """
        Inicjalizacja widoku logowania / rejestracji

        Args:
            parent: Rodzic (główne okno aplikacji)
        """
        super().__init__(parent, fg_color="transparent")

        self.controller = None
        self.mode = self.MODE_LOGIN

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
            pass

    def _create_right_panel(self):
        """Tworzy prawą stronę - formularz logowania / rejestracji"""
        self.right_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_RIGHT,
            corner_radius=0
        )
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        # Kontener wyśrodkowany
        self.form_container = ctk.CTkFrame(
            self.right_frame,
            fg_color="transparent"
        )
        self.form_container.place(relx=0.5, rely=0.5, anchor="center")

        # Nagłówek
        self.title_label = ctk.CTkLabel(
            self.form_container,
            text="Witamy ponownie!",
            font=Fonts.TITLE,
            text_color=Colors.TEXT_PRIMARY
        )
        self.title_label.pack(pady=(0, 6))

        self.subtitle_label = ctk.CTkLabel(
            self.form_container,
            text="Cieszymy się, że znów z nami jesteś!",
            font=Fonts.SUBTITLE,
            text_color=Colors.TEXT_SECONDARY
        )
        self.subtitle_label.pack(pady=(0, 20))

        # === POLE: NAZWA UŻYTKOWNIKA (REJESTRACJA) ===
        self.username_label_box = ctk.CTkFrame(self.form_container, fg_color="transparent")
        ctk.CTkLabel(self.username_label_box, text="👤", font=("Segoe UI", 14), text_color=Colors.ICON_COLOR).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(self.username_label_box, text="Nazwa użytkownika:", font=Fonts.LABEL, text_color=Colors.TEXT_LABEL).pack(side="left")

        self.username_entry = ctk.CTkEntry(
            self.form_container,
            width=320,
            height=42,
            font=Fonts.INPUT,
            fg_color=Colors.INPUT_BG,
            border_color=Colors.INPUT_BORDER,
            border_width=2,
            text_color=Colors.TEXT_INPUT,
            placeholder_text="Twój pseudonim"
        )

        # === POLE: EMAIL ===
        self.email_label_box = ctk.CTkFrame(self.form_container, fg_color="transparent")
        self.email_label_box.pack(fill="x", padx=2)
        ctk.CTkLabel(self.email_label_box, text="📧", font=("Segoe UI", 14), text_color=Colors.ICON_COLOR).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(self.email_label_box, text="Email:", font=Fonts.LABEL, text_color=Colors.TEXT_LABEL).pack(side="left")

        self.email_entry = ctk.CTkEntry(
            self.form_container,
            width=320,
            height=42,
            font=Fonts.INPUT,
            fg_color=Colors.INPUT_BG,
            border_color=Colors.INPUT_BORDER,
            border_width=2,
            text_color=Colors.TEXT_INPUT,
            placeholder_text="podaj@email.com"
        )
        self.email_entry.pack(pady=(4, 12))

        # === POLE: HASŁO ===
        self.password_label_box = ctk.CTkFrame(self.form_container, fg_color="transparent")
        self.password_label_box.pack(fill="x", padx=2)
        ctk.CTkLabel(self.password_label_box, text="🔐", font=("Segoe UI", 14), text_color=Colors.ICON_COLOR).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(self.password_label_box, text="Hasło:", font=Fonts.LABEL, text_color=Colors.TEXT_LABEL).pack(side="left")

        self.password_entry = ctk.CTkEntry(
            self.form_container,
            width=320,
            height=42,
            font=Fonts.INPUT,
            fg_color=Colors.INPUT_BG,
            border_color=Colors.INPUT_BORDER,
            border_width=2,
            text_color=Colors.TEXT_INPUT,
            placeholder_text="••••••••",
            show="•"
        )
        self.password_entry.pack(pady=(4, 12))

        # === POLE: POWTÓRZ HASŁO (REJESTRACJA) ===
        self.confirm_label_box = ctk.CTkFrame(self.form_container, fg_color="transparent")
        ctk.CTkLabel(self.confirm_label_box, text="🔒", font=("Segoe UI", 14), text_color=Colors.ICON_COLOR).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(self.confirm_label_box, text="Powtórz hasło:", font=Fonts.LABEL, text_color=Colors.TEXT_LABEL).pack(side="left")

        self.confirm_password_entry = ctk.CTkEntry(
            self.form_container,
            width=320,
            height=42,
            font=Fonts.INPUT,
            fg_color=Colors.INPUT_BG,
            border_color=Colors.INPUT_BORDER,
            border_width=2,
            text_color=Colors.TEXT_INPUT,
            placeholder_text="••••••••",
            show="•"
        )

        # Główny przycisk akcji (Logowanie / Rejestracja)
        self.submit_button = ctk.CTkButton(
            self.form_container,
            text="Zaloguj się",
            width=320,
            height=44,
            font=Fonts.BUTTON,
            fg_color=Colors.BUTTON_PRIMARY,
            hover_color=Colors.BUTTON_PRIMARY_HOVER,
            command=self._on_submit_click
        )
        self.submit_button.pack(pady=(8, 0))

        # Przełącznik trybu (Zaloguj <-> Zarejestruj)
        self.toggle_mode_button = ctk.CTkButton(
            self.form_container,
            text="Nie masz konta? Zarejestruj się",
            fg_color="transparent",
            hover_color=Colors.INPUT_BG,
            font=("Segoe UI", 12, "underline"),
            text_color=Colors.TEXT_SECONDARY,
            command=self._on_toggle_mode_click
        )
        self.toggle_mode_button.pack(pady=(10, 0))

        # Komunikat błędu / sukcesu
        self.status_label = ctk.CTkLabel(
            self.form_container,
            text="",
            font=Fonts.MESSAGE,
            text_color=Colors.ERROR
        )
        self.status_label.pack(pady=(8, 0))

    # ==========================================
    # PRZEŁĄCZANIE TRYBÓW (LOGIN <-> REJESTRACJA)
    # ==========================================

    def set_mode(self, mode: str):
        """Przełącza interfejs między logowaniem a rejestracją"""
        self.mode = mode
        self.clear_status()

        if mode == self.MODE_REGISTER:
            self.title_label.configure(text="Stwórz konto")
            self.subtitle_label.configure(text="Dołącz do społeczności Voxen!")
            self.submit_button.configure(text="Zarejestruj się")
            self.toggle_mode_button.configure(text="Masz już konto? Zaloguj się")

            # Przebudowa kolejności widgetów
            # 1. Schowaj wszystko
            for w in [self.email_label_box, self.email_entry, self.password_label_box, self.password_entry,
                     self.submit_button, self.toggle_mode_button, self.status_label]:
                w.pack_forget()

            # 2. Rozmieść w kolejności dla rejestracji
            self.username_label_box.pack(fill="x", padx=2)
            self.username_entry.pack(pady=(4, 10))

            self.email_label_box.pack(fill="x", padx=2)
            self.email_entry.pack(pady=(4, 10))

            self.password_label_box.pack(fill="x", padx=2)
            self.password_entry.pack(pady=(4, 10))

            self.confirm_label_box.pack(fill="x", padx=2)
            self.confirm_password_entry.pack(pady=(4, 14))

            self.submit_button.pack(pady=(6, 0))
            self.toggle_mode_button.pack(pady=(8, 0))
            self.status_label.pack(pady=(6, 0))

            self.username_entry.focus()

        else:
            self.title_label.configure(text="Witamy ponownie!")
            self.subtitle_label.configure(text="Cieszymy się, że znów z nami jesteś!")
            self.submit_button.configure(text="Zaloguj się")
            self.toggle_mode_button.configure(text="Nie masz konta? Zarejestruj się")

            # Ukryj pola rejestracji
            self.username_label_box.pack_forget()
            self.username_entry.pack_forget()
            self.confirm_label_box.pack_forget()
            self.confirm_password_entry.pack_forget()

            # Przywróć układ logowania
            for w in [self.email_label_box, self.email_entry, self.password_label_box, self.password_entry,
                     self.submit_button, self.toggle_mode_button, self.status_label]:
                w.pack_forget()

            self.email_label_box.pack(fill="x", padx=2)
            self.email_entry.pack(pady=(4, 12))

            self.password_label_box.pack(fill="x", padx=2)
            self.password_entry.pack(pady=(4, 14))

            self.submit_button.pack(pady=(8, 0))
            self.toggle_mode_button.pack(pady=(10, 0))
            self.status_label.pack(pady=(8, 0))

            self.email_entry.focus()

    def _on_toggle_mode_click(self):
        """Zmienia tryb logowanie / rejestracja"""
        new_mode = self.MODE_REGISTER if self.mode == self.MODE_LOGIN else self.MODE_LOGIN
        self.set_mode(new_mode)

    def _on_submit_click(self):
        """Deleguje akcję zatwierdzenia do kontrolera w zależności od trybu"""
        if not self.controller:
            return

        if self.mode == self.MODE_REGISTER:
            self.controller.handle_register()
        else:
            self.controller.handle_login()

    # ==========================================
    # SKRÓTY KLAWISZOWE (ENTER NAVIGATION)
    # ==========================================

    def setup_key_bindings(self):
        """Konfiguruje nawigację klawiszem Enter między polami formularza"""
        self.username_entry.bind('<Return>', lambda e: self.email_entry.focus())
        self.email_entry.bind('<Return>', lambda e: self.password_entry.focus())
        self.password_entry.bind('<Return>', self._on_password_enter)
        self.confirm_password_entry.bind('<Return>', lambda e: self._on_submit_click())

    def _on_password_enter(self, event):
        """Enter w haśle: jeśli rejestracja -> do potwierdzenia, jeśli login -> submit"""
        if self.mode == self.MODE_REGISTER:
            self.confirm_password_entry.focus()
        else:
            self._on_submit_click()

    def set_controller(self, controller):
        """Ustawia controller i konfiguruje bindingi"""
        self.controller = controller
        self.setup_key_bindings()

    # ==========================================
    # PUBLICZNE METODY FORMULARZA
    # ==========================================

    def get_login_credentials(self):
        """Zwraca dane formularza logowania (email, password)"""
        return self.email_entry.get().strip(), self.password_entry.get()

    def get_register_credentials(self):
        """Zwraca dane formularza rejestracji (username, email, password, confirm_password)"""
        return (
            self.username_entry.get().strip(),
            self.email_entry.get().strip(),
            self.password_entry.get(),
            self.confirm_password_entry.get()
        )

    # Zachowanie wstecznej kompatybilności
    def get_credentials(self):
        return self.get_login_credentials()

    def show_error(self, message: str):
        """Wyświetla błąd na czerwono"""
        self.status_label.configure(text=message, text_color=Colors.ERROR)

    def show_success(self, message: str):
        """Wyświetla sukces na zielono"""
        self.status_label.configure(text=message, text_color=Colors.SUCCESS)

    def clear_status(self):
        """Czyści komunikaty statusu"""
        self.status_label.configure(text="")
