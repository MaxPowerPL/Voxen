"""
VIEW - Główny ekran aplikacji (Discord-like)
"""
import customtkinter as ctk
from utils import Colors, Fonts
from PIL import Image, ImageDraw


class AppView(ctk.CTkFrame):
    """Główny widok aplikacji w stylu Discord (View w MVC)"""

    def __init__(self, parent, user_data):
        """
        Inicjalizacja głównego widoku

        Args:
            parent: Główne okno aplikacji
            user_data: Dane zalogowanego użytkownika
        """
        super().__init__(parent, fg_color=Colors.BG_MAIN)

        self.user_data = user_data

        # Konfiguracja grid - 3 kolumny (serwery | kanały | czat)
        self.grid_columnconfigure(0, weight=0, minsize=72)    # Serwery (stała szerokość)
        self.grid_columnconfigure(1, weight=0, minsize=240)   # Kanały/DMs (stała szerokość)
        self.grid_columnconfigure(2, weight=1)                # Czat (rozciągliwy)
        self.grid_rowconfigure(0, weight=1)

        # Utwórz sekcje
        self._create_servers_sidebar()
        self._create_channels_sidebar()
        self._create_chat_area()

    # ==========================================
    # LEWA KOLUMNA - SERWERY (jak Discord)
    # ==========================================

    def _create_servers_sidebar(self):
        """Tworzy lewą kolumnę z ikonami serwerów"""
        self.servers_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SIDEBAR,
            corner_radius=0,
            width=72
        )
        self.servers_frame.grid(row=0, column=0, sticky="nsew")
        self.servers_frame.grid_propagate(False)

        # Scrollable frame dla serwerów (NIEWIDOCZNY SCROLLBAR)
        self.servers_scroll = ctk.CTkScrollableFrame(
            self.servers_frame,
            fg_color="transparent",
            width=60,
            scrollbar_button_color=Colors.BG_SIDEBAR,
            scrollbar_button_hover_color=Colors.BG_SIDEBAR
        )
        self.servers_scroll.pack(fill="both", expand=True, padx=6, pady=8)

        # === PRZYCISK HOME (DM) ===
        self.home_button = self._create_server_button("🏠", "Direct Messages", icon_type="text")
        self.home_button.pack(pady=(0, 8))

        # === SEPARATOR ===
        separator = ctk.CTkFrame(
            self.servers_scroll,
            height=2,
            fg_color=Colors.INPUT_BORDER
        )
        separator.pack(fill="x", pady=8)

        # === VOXEN OFFICIAL - Z LOGO ===
        voxen_btn = self._create_server_button(
            "assets/images/logo.ico",
            "Voxen Official",
            icon_type="image"
        )
        voxen_btn.pack(pady=4)

        # === PRZYKŁADOWE SERWERY - Z EMOJI ===
        servers = [
            ("🎮", "Gaming"),
            ("💻", "Coding"),
            ("🎵", "Music"),
            ("🎨", "Art"),
        ]

        for icon, name in servers:
            btn = self._create_server_button(icon, name, icon_type="text")
            btn.pack(pady=4)

        # === PRZYCISK DODAJ SERWER ===
        add_server_btn = self._create_server_button("+", "Dodaj serwer", is_add=True, icon_type="text")
        add_server_btn.pack(pady=(16, 0))

    def _create_circular_mask(self, size):
        """Tworzy okrągłą maskę dla obrazka"""
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        return mask

    def _create_server_button(self, icon, tooltip, is_add=False, icon_type="text"):
        """
        Tworzy przycisk serwera (okrągły jak Discord) - NAPRAWIONE!

        Args:
            icon: Ikona/tekst/ścieżka do obrazka
            tooltip: Tooltip po najechaniu
            is_add: Czy to przycisk dodawania
            icon_type: "text" lub "image" - typ ikony
        """
        color = Colors.BUTTON_ADD if is_add else Colors.BG_MAIN
        hover_color = Colors.BUTTON_PRIMARY if is_add else Colors.BUTTON_SECONDARY

        # ✅ KONTENER - Idealny kwadrat 48x48
        button_container = ctk.CTkFrame(
            self.servers_scroll,
            fg_color="transparent",
            width=48,
            height=48
        )
        button_container.pack_propagate(False)

        if icon_type == "image":
            # ✅ PRZYCISK Z OBRAZKIEM (logo)
            try:
                from PIL import Image

                # Załaduj obrazek
                logo_img = Image.open(icon).convert("RGBA")

                # Przeskaluj do 36x36
                logo_img = logo_img.resize((36, 36), Image.Resampling.LANCZOS)

                # Zastosuj okrągłą maskę
                mask = self._create_circular_mask(36)
                output = Image.new('RGBA', (36, 36), (0, 0, 0, 0))
                output.paste(logo_img, (0, 0))
                output.putalpha(mask)

                # Stwórz CTkImage
                logo_ctk = ctk.CTkImage(
                    light_image=output,
                    dark_image=output,
                    size=(36, 36)
                )

                # ✅ UŻYJ CTkButton z obrazkiem (corner_radius działa!)
                btn = ctk.CTkButton(
                    button_container,
                    text="",  # Pusty tekst
                    image=logo_ctk,
                    width=48,
                    height=48,
                    corner_radius=24,  # ✅ TERAZ DZIAŁA!
                    fg_color=color,
                    hover_color=hover_color,
                    border_width=0,
                    command=lambda: self._on_server_click(tooltip)
                )
                btn.place(relx=0.5, rely=0.5, anchor="center")

            except Exception as e:
                print(f"Błąd ładowania logo: {e}")
                # Fallback do tekstu "V"
                btn = ctk.CTkButton(
                    button_container,
                    text="V",
                    width=48,
                    height=48,
                    corner_radius=24,
                    fg_color=color,
                    hover_color=hover_color,
                    font=("Segoe UI", 18, "bold"),
                    text_color=Colors.TEXT_PRIMARY,
                    border_width=0,
                    command=lambda: self._on_server_click(tooltip)
                )
                btn.place(relx=0.5, rely=0.5, anchor="center")
        else:
            # ✅ PRZYCISK Z TEKSTEM/EMOJI
            btn = ctk.CTkButton(
                button_container,
                text=icon,
                width=48,
                height=48,
                corner_radius=24,  # ✅ TERAZ DZIAŁA!
                fg_color=color,
                hover_color=hover_color,
                font=("Segoe UI", 18, "bold"),
                text_color=Colors.TEXT_PRIMARY,
                border_width=0,
                command=lambda: self._on_server_click(tooltip)
            )
            btn.place(relx=0.5, rely=0.5, anchor="center")

        return button_container

    def _on_server_click(self, server_name):
        """Obsługuje kliknięcie serwera"""
        print(f"Wybrano serwer: {server_name}")
        # TODO: Załaduj kanały dla tego serwera

    # ==========================================
    # ŚRODKOWA KOLUMNA - KANAŁY/KONWERSACJE
    # ==========================================

    def _create_channels_sidebar(self):
        """Tworzy środkową kolumnę z listą kanałów/DMs"""
        self.channels_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SECONDARY,
            corner_radius=0,
            width=240
        )
        self.channels_frame.grid(row=0, column=1, sticky="nsew")
        self.channels_frame.grid_propagate(False)

        # === HEADER Z NAZWĄ SERWERA ===
        header = ctk.CTkFrame(
            self.channels_frame,
            fg_color=Colors.BG_MAIN,
            height=48,
            corner_radius=0
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        server_name_label = ctk.CTkLabel(
            header,
            text="🏠  Znajomi",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        server_name_label.pack(side="left", padx=16, fill="both", expand=True)

        # === SEARCH BAR ===
        search_frame = ctk.CTkFrame(
            self.channels_frame,
            fg_color="transparent",
            height=56
        )
        search_frame.pack(fill="x", padx=12, pady=8)

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍  Szukaj",
            height=32,
            font=Fonts.INPUT,
            fg_color=Colors.BG_MAIN,
            border_width=0
        )
        self.search_entry.pack(fill="x")

        # === TABS (Dostępni, Oczekujący, Zablokowane) ===
        tabs_frame = ctk.CTkFrame(
            self.channels_frame,
            fg_color="transparent",
            height=40
        )
        tabs_frame.pack(fill="x", padx=8)

        tabs = ["Znajomi", "Oczekujący", "Dostępni", "Wszystkie"]
        for tab in tabs:
            tab_btn = ctk.CTkButton(
                tabs_frame,
                text=tab,
                height=28,
                fg_color="transparent",
                hover_color=Colors.BG_MAIN,
                font=Fonts.LABEL,
                text_color=Colors.TEXT_SECONDARY,
                corner_radius=4,
                command=lambda t=tab: self._on_tab_click(t)
            )
            tab_btn.pack(side="left", padx=2)

        # === SEPARATOR ===
        separator = ctk.CTkFrame(
            self.channels_frame,
            height=2,
            fg_color=Colors.INPUT_BORDER
        )
        separator.pack(fill="x", pady=8)

        # === LISTA KONWERSACJI (SCROLLABLE) - CIEŃSZY SCROLLBAR ===
        self.conversations_scroll = ctk.CTkScrollableFrame(
            self.channels_frame,
            fg_color="transparent",
            scrollbar_button_color=Colors.INPUT_BORDER,
            scrollbar_button_hover_color=Colors.BG_MAIN,
            scrollbar_fg_color=Colors.BG_SECONDARY
        )
        self.conversations_scroll.pack(fill="both", expand=True, padx=8)

        # ✅ Zmniejsz szerokość scrollbara
        self.conversations_scroll._scrollbar.configure(width=15)

        # Dodaj przykładowe konwersacje
        self._populate_conversations()

        # === USER PANEL NA DOLE ===
        self._create_user_panel()

    def _populate_conversations(self):
        """Wypełnia listę konwersacji"""
        conversations = [
            ("👤", "Wincekk", "online", True),
            ("👤", "Maxi3049", "idle", False),
            ("👤", "Nemeczek", "online", False),
            ("🤖", "Unity Bot", "online", False),
            ("👤", "Kapi", "dnd", False),
            ("👤", "Chaos", "offline", False),
        ]

        for avatar, name, status, is_active in conversations:
            self._create_conversation_item(avatar, name, status, is_active)

    def _create_conversation_item(self, avatar, name, status, is_active=False):
        """Tworzy element listy konwersacji"""
        bg_color = Colors.BG_MAIN if is_active else "transparent"

        item = ctk.CTkFrame(
            self.conversations_scroll,
            fg_color=bg_color,
            height=42,
            corner_radius=8
        )
        item.pack(fill="x", pady=2)

        # Avatar
        avatar_label = ctk.CTkLabel(
            item,
            text=avatar,
            font=("Segoe UI", 24),
            width=40
        )
        avatar_label.pack(side="left", padx=(8, 12))

        # Nazwa i status
        text_container = ctk.CTkFrame(item, fg_color="transparent")
        text_container.pack(side="left", fill="both", expand=True)

        name_label = ctk.CTkLabel(
            text_container,
            text=name,
            font=Fonts.LABEL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        name_label.pack(anchor="w")

        # ✅ Status z kolorową kropką (oddzielnie)
        status_container = ctk.CTkFrame(text_container, fg_color="transparent")
        status_container.pack(anchor="w")

        # Mapa statusów na kolory i teksty
        status_config = {
            "online": (Colors.ONLINE, "Online"),
            "idle": (Colors.IDLE, "Zaraz wracam"),
            "dnd": (Colors.DND, "Nie przeszkadzać"),
            "offline": (Colors.OFFLINE, "Offline")
        }

        color, text = status_config.get(status, (Colors.OFFLINE, "Offline"))

        # Kropka (wyrównana)
        status_dot = ctk.CTkLabel(
            status_container,
            text="🟢",
            font=("Segoe UI", 10),
            text_color=color,
            width=10,
            anchor="w"
        )
        status_dot.pack(side="left", pady=(2, 0))

        # Tekst statusu
        status_text = ctk.CTkLabel(
            status_container,
            text=text,
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        )
        status_text.pack(side="left", padx=(2, 0))

        # Klik
        item.bind("<Button-1>", lambda e: self._on_conversation_click(name))

    def _on_conversation_click(self, name):
        """Obsługuje kliknięcie konwersacji"""
        print(f"Otwarto konwersację z: {name}")
        self.chat_title.configure(text=f"💬  {name}")

    def _on_tab_click(self, tab_name):
        """Obsługuje kliknięcie taba"""
        print(f"Wybrano tab: {tab_name}")

    def _create_user_panel(self):
        """Tworzy panel użytkownika na dole kanałów"""
        user_panel = ctk.CTkFrame(
            self.channels_frame,
            fg_color=Colors.BG_MAIN,
            height=52,
            corner_radius=0
        )
        user_panel.pack(fill="x", side="bottom")
        user_panel.pack_propagate(False)

        # Avatar
        avatar = ctk.CTkLabel(
            user_panel,
            text="👤",
            font=("Segoe UI", 28),
            width=40
        )
        avatar.pack(side="left", padx=(8, 8))

        # User info
        user_info = ctk.CTkFrame(user_panel, fg_color="transparent")
        user_info.pack(side="left", fill="both", expand=True)

        username = ctk.CTkLabel(
            user_info,
            text=self.user_data.get("email", "User").split("@")[0],
            font=Fonts.LABEL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        username.pack(anchor="w", pady=(4, 0))

        # ✅ Status z kolorową kropką (oddzielnie)
        status_container = ctk.CTkFrame(user_info, fg_color="transparent")
        status_container.pack(anchor="w")

        # Kropka (wyrównana)
        status_dot = ctk.CTkLabel(
            status_container,
            text="🟢",
            font=("Segoe UI", 10),
            text_color=Colors.ONLINE,
            width=10,
            anchor="w"
        )
        status_dot.pack(side="left", pady=(2, 0))

        # Tekst "Online"
        status_text = ctk.CTkLabel(
            status_container,
            text="Online",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        )
        status_text.pack(side="left", padx=(2, 0))

        # Przyciski ustawień
        settings_btn = ctk.CTkButton(
            user_panel,
            text="⚙️",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=Colors.BG_SECONDARY,
            font=("Segoe UI", 16),
            command=self._on_settings_click
        )
        settings_btn.pack(side="right", padx=4)

    def _on_settings_click(self):
        """Otwiera ustawienia"""
        print("Otwarto ustawienia")

    # ==========================================
    # PRAWA KOLUMNA - OBSZAR CZATU
    # ==========================================

    def _create_chat_area(self):
        """Tworzy główny obszar czatu"""
        self.chat_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_RIGHT,
            corner_radius=0
        )
        self.chat_frame.grid(row=0, column=2, sticky="nsew")

        # === HEADER CZATU ===
        chat_header = ctk.CTkFrame(
            self.chat_frame,
            fg_color=Colors.BG_MAIN,
            height=48,
            corner_radius=0
        )
        chat_header.pack(fill="x")
        chat_header.pack_propagate(False)

        self.chat_title = ctk.CTkLabel(
            chat_header,
            text="💬  Wybierz konwersację",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        self.chat_title.pack(side="left", padx=16, fill="both", expand=True)

        # === OBSZAR WIADOMOŚCI (SCROLLABLE) - CIEŃSZY SCROLLBAR ===
        self.messages_scroll = ctk.CTkScrollableFrame(
            self.chat_frame,
            fg_color="transparent",
            scrollbar_button_color=Colors.INPUT_BORDER,
            scrollbar_button_hover_color=Colors.BG_MAIN,
            scrollbar_fg_color=Colors.BG_RIGHT
        )
        self.messages_scroll.pack(fill="both", expand=True, padx=16, pady=16)

        # ✅ Zmniejsz szerokość scrollbara
        self.messages_scroll._scrollbar.configure(width=15)

        # Przykładowa wiadomość powitalna
        welcome_label = ctk.CTkLabel(
            self.messages_scroll,
            text=f"Witaj, {self.user_data.get('email', 'User').split('@')[0]}! 👋\n\nWybierz konwersację z lewej strony.",
            font=Fonts.SUBTITLE,
            text_color=Colors.TEXT_SECONDARY,
            justify="center"
        )
        welcome_label.pack(pady=100)

        # === INPUT DO WPISYWANIA WIADOMOŚCI ===
        self._create_message_input()

    def _create_message_input(self):
        """Tworzy pole do wpisywania wiadomości"""
        input_container = ctk.CTkFrame(
            self.chat_frame,
            fg_color="transparent",
            height=68
        )
        input_container.pack(fill="x", padx=16, pady=(0, 16))
        input_container.pack_propagate(False)

        # Frame z inputem (jak Discord)
        input_frame = ctk.CTkFrame(
            input_container,
            fg_color=Colors.INPUT_BG,
            corner_radius=8,
            height=44
        )
        input_frame.pack(fill="both", expand=True)

        # Przycisk dodaj plik
        attach_btn = ctk.CTkButton(
            input_frame,
            text="➕",
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            font=("Segoe UI", 18),
            command=self._on_attach_click
        )
        attach_btn.pack(side="left", padx=8)

        # Entry
        self.message_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Napisz wiadomość...",
            font=Fonts.INPUT,
            fg_color="transparent",
            border_width=0
        )
        self.message_entry.pack(side="left", fill="both", expand=True, padx=8)
        self.message_entry.bind("<Return>", self._on_send_message)

        # Przycisk emoji
        emoji_btn = ctk.CTkButton(
            input_frame,
            text="😊",
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            font=("Segoe UI", 18),
            command=self._on_emoji_click
        )
        emoji_btn.pack(side="right", padx=4)

    def _on_send_message(self, event=None):
        """Wysyła wiadomość"""
        message = self.message_entry.get().strip()
        if message:
            print(f"Wysłano: {message}")
            self.message_entry.delete(0, "end")
            # TODO: Dodaj wiadomość do czatu

    def _on_attach_click(self):
        """Otwiera dialog wyboru pliku"""
        print("Wybierz plik do wysłania")

    def _on_emoji_click(self):
        """Otwiera picker emoji"""
        print("Otwarto picker emoji")
