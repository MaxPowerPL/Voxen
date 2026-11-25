"""
VIEW - Główny ekran aplikacji (Discord-like)
"""

import customtkinter as ctk
from utils import Colors, Fonts
from PIL import Image, ImageDraw
from views.components import VirtualChatView

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
        self.controller = None

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
        self.home_button = self._create_server_button("🏠", "Direct Messages", icon_type="text", server_id=None)
        self.home_button.pack(pady=(0, 8))

        # === SEPARATOR ===
        separator = ctk.CTkFrame(
            self.servers_scroll,
            height=2,
            fg_color=Colors.INPUT_BORDER
        )
        separator.pack(fill="x", pady=8)

        # Kontener na dynamicznie ładowane serwery z SQLite
        self.dynamic_servers_frame = ctk.CTkFrame(
            self.servers_scroll,
            fg_color="transparent"
        )
        self.dynamic_servers_frame.pack(fill="x")

        # === PRZYCISK DODAJ SERWER (+) ===
        self.add_server_btn = self._create_server_button("+", "Dodaj serwer", is_add=True, icon_type="text", server_id="add")
        self.add_server_btn.pack(pady=(12, 0))

    def _create_circular_mask(self, size):
        """Tworzy okrągłą maskę dla obrazka"""
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        return mask

    def _create_server_button(self, icon, tooltip, is_add=False, icon_type="text", server_id=None, parent_frame=None):
        """
        Tworzy przycisk serwera (okrągły jak Discord) wraz ze wskaźnikiem nieprzeczytanych wiadomości

        Args:
            icon: Ikona/tekst/ścieżka do obrazka
            tooltip: Tooltip po najechaniu
            is_add: Czy to przycisk dodawania
            icon_type: "text" lub "image" - typ ikony
            server_id: Identyfikator serwera w bazie danych
            parent_frame: Opcjonalna ramka rodzica
        """
        color = Colors.BUTTON_ADD if is_add else Colors.BG_MAIN
        hover_color = Colors.BUTTON_PRIMARY if is_add else Colors.BUTTON_SECONDARY
        parent = parent_frame or self.servers_scroll

        button_container = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            width=48,
            height=48
        )
        button_container.pack_propagate(False)

        if is_add:
            cmd = self._on_add_server_click
        else:
            cmd = lambda sid=server_id, name=tooltip: self._on_server_click(sid, name)

        if icon_type == "image":
            try:
                from PIL import Image
                logo_img = Image.open(icon).convert("RGBA")
                logo_img = logo_img.resize((36, 36), Image.Resampling.LANCZOS)
                mask = self._create_circular_mask(36)
                output = Image.new('RGBA', (36, 36), (0, 0, 0, 0))
                output.paste(logo_img, (0, 0))
                output.putalpha(mask)

                logo_ctk = ctk.CTkImage(
                    light_image=output,
                    dark_image=output,
                    size=(36, 36)
                )

                btn = ctk.CTkButton(
                    button_container,
                    text="",
                    image=logo_ctk,
                    width=48,
                    height=48,
                    corner_radius=24,
                    fg_color=color,
                    hover_color=hover_color,
                    border_width=0,
                    command=cmd
                )
                btn.place(relx=0.5, rely=0.5, anchor="center")

            except Exception:
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
                    command=cmd
                )
                btn.place(relx=0.5, rely=0.5, anchor="center")
        else:
            btn = ctk.CTkButton(
                button_container,
                text=icon,
                width=48,
                height=48,
                corner_radius=24,
                fg_color=color,
                hover_color=hover_color,
                font=("Segoe UI", 18, "bold"),
                text_color=Colors.TEXT_PRIMARY,
                border_width=0,
                command=cmd
            )
            btn.place(relx=0.5, rely=0.5, anchor="center")

        # Odznaka (Badge) nieprzeczytanych wiadomości dla serwera / DMs
        if server_id != "add":
            badge_frame = ctk.CTkFrame(
                button_container,
                fg_color=Colors.ERROR,
                width=20,
                height=20,
                corner_radius=10
            )
            badge_lbl = ctk.CTkLabel(
                badge_frame,
                text="",
                font=("Segoe UI", 9, "bold"),
                text_color="#ffffff"
            )
            badge_lbl.place(relx=0.5, rely=0.5, anchor="center")

            key = server_id if server_id is not None else "dms"
            if not hasattr(self, "server_badges"):
                self.server_badges = {}
            self.server_badges[key] = (badge_frame, badge_lbl)

        return button_container

    def _on_server_click(self, server_id, server_name):
        """Deleguje do controllera"""
        if self.controller:
            self.controller.handle_server_click(server_id, server_name)

    def _on_add_server_click(self):
        """Deleguje kliknięcie przycisku dodania serwera"""
        if self.controller:
            self.controller.handle_add_server_click()

    def _on_channel_click(self, server_id, channel_name, topic=""):
        """Deleguje kliknięcie kanału tekstowego"""
        if self.controller:
            self.controller.handle_channel_click(server_id, channel_name, topic)

    def _on_add_channel_click(self):
        """Deleguje kliknięcie przycisku dodania kanału"""
        if self.controller and hasattr(self, 'current_server_id'):
            self.controller.handle_add_channel_click(self.current_server_id)

    def _on_manage_members_click(self):
        """Delegates server member management to the controller."""
        if self.controller and hasattr(self, "current_server_id"):
            self.controller.handle_manage_members_click(self.current_server_id)

    # ==========================================
    # ŚRODKOWA KOLUMNA - KANAŁY / DMs
    # ==========================================

    def _create_channels_sidebar(self):
        """Tworzy środkową kolumnę z dynamicznymi kanałami / DMs"""
        self.channels_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SECONDARY,
            corner_radius=0,
            width=240
        )
        self.channels_frame.grid(row=0, column=1, sticky="nsew")
        self.channels_frame.grid_propagate(False)

        # === HEADER Z NAZWĄ SERWERA ===
        self.channels_header = ctk.CTkFrame(
            self.channels_frame,
            fg_color=Colors.BG_MAIN,
            height=48,
            corner_radius=0
        )
        self.channels_header.pack(fill="x")
        self.channels_header.pack_propagate(False)

        self.server_name_label = ctk.CTkLabel(
            self.channels_header,
            text="🏠 Znajomi",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        self.server_name_label.pack(side="left", padx=16, fill="both", expand=True)

        self.manage_members_button = ctk.CTkButton(
            self.channels_header,
            text="👥",
            width=36,
            height=32,
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            command=self._on_manage_members_click
        )
        self.manage_members_button.pack(side="right", padx=10)
        self.manage_members_button.configure(state="disabled")

        # === USER PANEL NA SAMYM DOLE (STAŁY) ===
        self._create_user_panel()

        # === 1. PANEL DLA DIRECT MESSAGES (ZNAJOMI) ===
        self.dms_panel = ctk.CTkFrame(self.channels_frame, fg_color="transparent")
        self._setup_dms_panel()

        # === 2. PANEL DLA KANAŁÓW SERWERA ===
        self.server_channels_panel = ctk.CTkFrame(self.channels_frame, fg_color="transparent")
        self._setup_server_channels_panel()

        # Domyślnie pokazujemy Direct Messages
        self.dms_panel.pack(fill="both", expand=True)

    def _setup_dms_panel(self):
        """Konfiguruje panel dla wiadomości bezpośrednich (DMs)"""
        search_frame = ctk.CTkFrame(self.dms_panel, fg_color="transparent", height=48)
        search_frame.pack(fill="x", padx=12, pady=(8, 4))

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Szukaj",
            height=32,
            font=Fonts.INPUT,
            fg_color=Colors.BG_MAIN,
            border_width=0
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        tabs_frame = ctk.CTkFrame(self.dms_panel, fg_color="transparent", height=36)
        tabs_frame.pack(fill="x", padx=8, pady=(0, 4))

        for tab in ["Znajomi", "Oczekujący", "Dostępni"]:
            ctk.CTkButton(
                tabs_frame,
                text=tab,
                height=26,
                fg_color="transparent",
                hover_color=Colors.BG_MAIN,
                font=Fonts.LABEL,
                text_color=Colors.TEXT_SECONDARY,
                corner_radius=4,
                command=lambda t=tab: self._on_tab_click(t)
            ).pack(side="left", padx=2)

        separator = ctk.CTkFrame(self.dms_panel, height=2, fg_color=Colors.INPUT_BORDER)
        separator.pack(fill="x", pady=4)

        self.conversations_scroll = ctk.CTkScrollableFrame(
            self.dms_panel,
            fg_color="transparent",
            scrollbar_button_color=Colors.INPUT_BORDER,
            scrollbar_button_hover_color=Colors.BG_MAIN,
            scrollbar_fg_color=Colors.BG_SECONDARY
        )
        self.conversations_scroll.pack(fill="both", expand=True, padx=8)
        self.conversations_scroll._scrollbar.configure(width=12)

        self._populate_conversations()

    def _setup_server_channels_panel(self):
        """Konfiguruje panel dla kanałów tekstowych serwera"""
        category_header = ctk.CTkFrame(self.server_channels_panel, fg_color="transparent", height=32)
        category_header.pack(fill="x", padx=12, pady=(10, 4))
        category_header.pack_propagate(False)

        cat_lbl = ctk.CTkLabel(
            category_header,
            text="📢  KANAŁY TEKSTOWE",
            font=("Segoe UI", 11, "bold"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        )
        cat_lbl.pack(side="left", fill="both", expand=True)

        add_channel_btn = ctk.CTkButton(
            category_header,
            text="+",
            width=22,
            height=22,
            font=("Segoe UI", 14, "bold"),
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            text_color=Colors.TEXT_SECONDARY,
            command=self._on_add_channel_click
        )
        add_channel_btn.pack(side="right")
        self.add_channel_button = add_channel_btn

        self.channels_scroll = ctk.CTkScrollableFrame(
            self.server_channels_panel,
            fg_color="transparent",
            scrollbar_button_color=Colors.INPUT_BORDER,
            scrollbar_button_hover_color=Colors.BG_MAIN,
            scrollbar_fg_color=Colors.BG_SECONDARY
        )
        self.channels_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.channels_scroll._scrollbar.configure(width=12)

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

        # Status z kolorową kropką
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

        # Kropka
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

        # Odznaka nieprzeczytanych wiadomości (Badge)
        badge_frame = ctk.CTkFrame(
            item,
            fg_color=Colors.ERROR,
            corner_radius=10,
            height=20
        )
        badge_label = ctk.CTkLabel(
            badge_frame,
            text="",
            font=("Segoe UI", 10, "bold"),
            text_color="#ffffff",
            padx=6
        )
        badge_label.pack(fill="both", expand=True)

        if not hasattr(self, "dm_badges"):
            self.dm_badges = {}
        self.dm_badges[name] = (badge_frame, badge_label)

        if not hasattr(self, "conversation_status_widgets"):
            self.conversation_status_widgets = {}
        self.conversation_status_widgets[name] = (status_dot, status_text)

        # Klik - deleguj do controllera
        def _click_handler(e=None):
            self._on_conversation_click(name)

        item.bind("<Button-1>", _click_handler)
        avatar_label.bind("<Button-1>", _click_handler)
        text_container.bind("<Button-1>", _click_handler)
        name_label.bind("<Button-1>", _click_handler)
        status_container.bind("<Button-1>", _click_handler)
        status_dot.bind("<Button-1>", _click_handler)
        status_text.bind("<Button-1>", _click_handler)
        badge_frame.bind("<Button-1>", _click_handler)
        badge_label.bind("<Button-1>", _click_handler)

    def _on_conversation_click(self, name):
        """Deleguje do controllera"""
        if self.controller:
            self.controller.handle_conversation_click(name)

    def _on_tab_click(self, tab_name):
        """Deleguje do controllera"""
        if self.controller:
            self.controller.handle_tab_click(tab_name)

    def _on_search(self, event):
        """Deleguje wyszukiwanie do controllera"""
        query = self.search_entry.get()
        if self.controller:
            self.controller.handle_search(query)

    def _on_history_search(self, event=None):
        """Delegates history search to the controller."""
        if not self.controller:
            return
        query = self.history_search_entry.get()
        sender = self.history_sender_entry.get()
        timestamp = self.history_timestamp_entry.get()
        self.controller.handle_history_search(query, sender=sender, timestamp=timestamp)

    def _create_user_panel(self):
        """Tworzy panel profilu użytkownika na dole kanałów z możliwością zmiany statusu"""
        self.user_panel = ctk.CTkFrame(
            self.channels_frame,
            fg_color=Colors.BG_MAIN,
            height=54,
            corner_radius=0
        )
        self.user_panel.pack(fill="x", side="bottom")
        self.user_panel.pack_propagate(False)

        # Klikalny obszar zmiany statusu
        user_clickable = ctk.CTkFrame(self.user_panel, fg_color="transparent")
        user_clickable.pack(side="left", fill="both", expand=True, padx=(4, 0))

        # Avatar
        self.my_avatar = ctk.CTkLabel(
            user_clickable,
            text="👤",
            font=("Segoe UI", 26),
            width=36
        )
        self.my_avatar.pack(side="left", padx=(4, 6))

        # User info
        user_info = ctk.CTkFrame(user_clickable, fg_color="transparent")
        user_info.pack(side="left", fill="both", expand=True)

        uname = self.user_data.get("username") or self.user_data.get("email", "User").split("@")[0]
        self.my_username = ctk.CTkLabel(
            user_info,
            text=uname,
            font=Fonts.LABEL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        self.my_username.pack(anchor="w", pady=(3, 0))

        # Status z kolorową kropką
        status_container = ctk.CTkFrame(user_info, fg_color="transparent")
        status_container.pack(anchor="w")

        # Kropka
        self.my_status_dot = ctk.CTkLabel(
            status_container,
            text="🟢",
            font=("Segoe UI", 10),
            text_color=Colors.ONLINE,
            width=10,
            anchor="w"
        )
        self.my_status_dot.pack(side="left", pady=(1, 0))

        # Tekst statusu
        self.my_status_text = ctk.CTkLabel(
            status_container,
            text="Dostępny",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        )
        self.my_status_text.pack(side="left", padx=(2, 0))

        # Podpięcie otwarcia modalu statusu
        def _open_status(e=None):
            self._on_status_menu_click()

        user_clickable.bind("<Button-1>", _open_status)
        self.my_avatar.bind("<Button-1>", _open_status)
        user_info.bind("<Button-1>", _open_status)
        self.my_username.bind("<Button-1>", _open_status)
        status_container.bind("<Button-1>", _open_status)
        self.my_status_dot.bind("<Button-1>", _open_status)
        self.my_status_text.bind("<Button-1>", _open_status)

        # Przyciski ustawień
        settings_btn = ctk.CTkButton(
            self.user_panel,
            text="⚙️",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=Colors.BG_SECONDARY,
            font=("Segoe UI", 16),
            command=self._on_settings_click
        )
        settings_btn.pack(side="right", padx=6)

    def _on_status_menu_click(self):
        """Deleguje otwarcie menu statusu do controllera"""
        if self.controller and hasattr(self.controller, "handle_status_menu_click"):
            self.controller.handle_status_menu_click()

    def update_my_status(self, status: str, custom_status: str = ""):
        """Aktualizuje wskaźnik statusu i tekst w dolnym panelu użytkownika"""
        from models.presence_tracker import PresenceTracker
        color, name, dot = PresenceTracker.get_status_info(status)
        display_text = custom_status if custom_status else name

        if hasattr(self, 'my_status_dot'):
            self.my_status_dot.configure(text=dot, text_color=color)
        if hasattr(self, 'my_status_text'):
            self.my_status_text.configure(text=display_text)

    def update_user_presence(self, username: str, status: str, custom_status: str = ""):
        """Aktualizuje wskaźnik statusu rozmówcy na liście Direct Messages"""
        if not hasattr(self, "conversation_status_widgets"):
            return
        if username not in self.conversation_status_widgets:
            return

        from models.presence_tracker import PresenceTracker
        color, name, dot = PresenceTracker.get_status_info(status)
        display_text = custom_status if custom_status else name

        dot_lbl, text_lbl = self.conversation_status_widgets[username]
        dot_lbl.configure(text=dot, text_color=color)
        text_lbl.configure(text=display_text)

    def show_status_selection_modal(self, current_status: str, current_custom_status: str, callback):
        """Wyświetla okno modalne wyboru statusu (Dostępny, Zaraz wracam, DND, Niewidoczny)"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Ustaw status obecności")
        dialog.geometry("400x480")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Ustaw status obecności",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(18, 2))

        ctk.CTkLabel(
            dialog,
            text="Wybierz jak chcesz być widoczny dla znajomych.",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY
        ).pack(pady=(0, 14))

        status_var = ctk.StringVar(value=current_status.lower() if current_status else "online")

        options_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        options_frame.pack(fill="x", padx=24, pady=4)

        from models.presence_tracker import PresenceTracker
        for skey, sinfo in PresenceTracker.STATUS_CONFIG.items():
            row = ctk.CTkFrame(options_frame, fg_color=Colors.BG_MAIN, corner_radius=8, height=48)
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)

            rb = ctk.CTkRadioButton(
                row,
                text=f"{sinfo['dot']}  {sinfo['name']}",
                value=skey,
                variable=status_var,
                font=("Segoe UI", 13, "bold"),
                text_color=Colors.TEXT_PRIMARY
            )
            rb.pack(side="left", padx=12, pady=6)

            desc = ctk.CTkLabel(
                row,
                text=sinfo["description"][:28] + ("..." if len(sinfo["description"]) > 28 else ""),
                font=("Segoe UI", 10),
                text_color=Colors.TEXT_SECONDARY
            )
            desc.pack(side="right", padx=12)

        # Własny status (Custom status)
        ctk.CTkLabel(
            dialog,
            text="WŁASNY STATUS (OPCJONALNIE)",
            font=("Segoe UI", 11, "bold"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        ).pack(fill="x", padx=24, pady=(12, 4))

        custom_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="np. 🎮 W grze, 💻 Koduję w Pythonie...",
            font=Fonts.INPUT
        )
        if current_custom_status:
            custom_entry.insert(0, current_custom_status)
        custom_entry.pack(fill="x", padx=24, pady=(0, 18))

        def _submit():
            sel_status = status_var.get()
            c_text = custom_entry.get().strip()
            dialog.destroy()
            callback(sel_status, c_text)

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=24, pady=(4, 12))

        ctk.CTkButton(
            btn_box,
            text="Anuluj",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=dialog.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_box,
            text="Zapisz status",
            fg_color=Colors.BUTTON_PRIMARY,
            hover_color=Colors.BUTTON_PRIMARY_HOVER,
            width=140,
            command=_submit
        ).pack(side="right")

    def _on_settings_click(self):
        """Deleguje do controllera"""
        if self.controller:
            self.controller.handle_settings_click()

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
            text="💬 Wybierz konwersację",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        self.chat_title.pack(side="left", padx=(16, 8), fill="both", expand=True)

        self.history_search_entry = ctk.CTkEntry(
            chat_header,
            placeholder_text="Szukaj w historii",
            width=150,
            height=30,
            fg_color=Colors.BG_RIGHT,
            border_width=0,
            font=Fonts.INPUT
        )
        self.history_search_entry.pack(side="right", padx=(4, 4))
        self.history_search_entry.bind("<KeyRelease>", self._on_history_search)

        self.history_sender_entry = ctk.CTkEntry(
            chat_header,
            placeholder_text="Nadawca",
            width=90,
            height=30,
            fg_color=Colors.BG_RIGHT,
            border_width=0,
            font=Fonts.INPUT
        )
        self.history_sender_entry.pack(side="right", padx=(4, 4))
        self.history_sender_entry.bind("<KeyRelease>", self._on_history_search)

        self.history_timestamp_entry = ctk.CTkEntry(
            chat_header,
            placeholder_text="Czas HH:MM",
            width=90,
            height=30,
            fg_color=Colors.BG_RIGHT,
            border_width=0,
            font=Fonts.INPUT
        )
        self.history_timestamp_entry.pack(side="right", padx=(4, 4))
        self.history_timestamp_entry.bind("<KeyRelease>", self._on_history_search)

        # Wskaźnik stanu sieci i latencji (Discord-like connection badge)
        self.net_status_label = ctk.CTkLabel(
            chat_header,
            text="🟢 Połączono",
            font=("Segoe UI", 11),
            text_color=Colors.ONLINE
        )
        self.net_status_label.pack(side="right", padx=16)

        # === OBSZAR WIADOMOŚCI - WIRTUALIZOWANY (OBJECT POOLING O(1)) ===
        self.virtual_chat = VirtualChatView(
            self.chat_frame,
            fg_color="transparent"
        )
        self.virtual_chat.pack(fill="both", expand=True, padx=16, pady=(12, 4))

        # === INPUT DO WPISYWANIA WIADOMOŚCI ===
        self._create_message_input()

    def _create_message_input(self):
        """Tworzy pole do wpisywania wiadomości"""
        input_container = ctk.CTkFrame(
            self.chat_frame,
            fg_color="transparent",
            height=74
        )
        input_container.pack(fill="x", padx=16, pady=(0, 16))
        input_container.pack_propagate(False)

        # Wskaźnik "pisze..." (typing indicator)
        self.typing_label = ctk.CTkLabel(
            input_container,
            text="",
            font=("Segoe UI", 11, "italic"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        )
        self.typing_label.pack(fill="x", padx=4, pady=(0, 2))

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
        self.message_entry.bind("<KeyRelease>", self._on_input_key)

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
        """Deleguje do controllera"""
        message = self.message_entry.get().strip()
        if self.controller:
            self.controller.handle_send_message(message)

    def _on_input_key(self, event):
        """Obsługuje wprowadzanie znaków w polu wiadomości"""
        # Ignoruj klawisze funkcyjne, nawigacyjne i modyfikatory
        if event.keysym in ["Return", "Shift_L", "Shift_R", "Control_L", "Control_R", 
                            "Alt_L", "Alt_R", "Caps_Lock", "Escape", "Tab", "Up", "Down", "Left", "Right"]:
            return

        text = self.message_entry.get().strip()
        if text and self.controller and hasattr(self.controller, "handle_user_typing"):
            self.controller.handle_user_typing()
        elif not text and self.controller and hasattr(self.controller, "handle_user_stop_typing"):
            self.controller.handle_user_stop_typing()

    def _on_attach_click(self):
        """Deleguje do controllera"""
        if self.controller:
            self.controller.handle_attach_click()

    def _on_emoji_click(self):
        """Deleguje do controllera"""
        if self.controller:
            self.controller.handle_emoji_click()

    # ==========================================
    # PUBLICZNE METODY DLA CONTROLLERA
    # ==========================================

    def set_controller(self, controller):
        """
        Ustawia controller

        Args:
            controller: Instancja AppController
        """
        self.controller = controller
        if hasattr(self, "virtual_chat"):
            self.virtual_chat.set_reaction_callback(
                lambda message_id, emoji: controller.handle_message_reaction(message_id, emoji)
            )

    def update_channels_header(self, text):
        """Aktualizuje nagłówek sekcji kanałów"""
        self.server_name_label.configure(text=text)

    def update_chat_title(self, text, topic=""):
        """Aktualizuje tytuł czatu i opcjonalny temat kanału"""
        if topic:
            self.chat_title.configure(text=f"{text}  |  {topic}")
        else:
            self.chat_title.configure(text=text)

    def render_servers(self, servers_list: list):
        """Dynamicznie renderuje serwery pobrane z SQLite w lewej kolumnie"""
        for child in self.dynamic_servers_frame.winfo_children():
            child.destroy()

        for s in servers_list:
            s_id = s.get("id")
            s_name = s.get("name", "Server")
            s_icon = s.get("icon", "📁")
            icon_type = "image" if ("." in s_icon or "/" in s_icon) else "text"

            btn = self._create_server_button(
                icon=s_icon,
                tooltip=s_name,
                is_add=False,
                icon_type=icon_type,
                server_id=s_id,
                parent_frame=self.dynamic_servers_frame
            )
            btn.pack(pady=4)

    def set_server_role_permissions(self, role: str, can_manage: bool) -> None:
        """Updates server-management controls for the current member role."""
        if hasattr(self, "add_channel_button"):
            self.add_channel_button.configure(state="normal" if can_manage else "disabled")
        if hasattr(self, "manage_members_button"):
            self.manage_members_button.configure(state="normal" if can_manage else "disabled")
        if hasattr(self, "virtual_chat"):
            can_moderate = role in ("owner", "admin", "moderator")
            self.virtual_chat.set_moderation_callback(
                getattr(self.controller, "handle_delete_message", None),
                enabled=can_moderate
            )
        role_labels = {
            "owner": "Właściciel",
            "admin": "Administrator",
            "moderator": "Moderator",
            "member": "Członek"
        }
        if hasattr(self, "server_name_label"):
            current = self.server_name_label.cget("text")
            if " • " not in current:
                self.server_name_label.configure(text=f"{current} • {role_labels.get(role, 'Członek')}")

    def show_server_channels(self, server_id: int, server_name: str, channels_list: list):
        """Przełącza środkowy panel na listę kanałów wybranego serwera"""
        self.current_server_id = server_id
        self.server_name_label.configure(text=f"📁 {server_name}")

        self.dms_panel.pack_forget()
        self.server_channels_panel.pack(fill="both", expand=True)

        for w in self.channels_scroll.winfo_children():
            w.destroy()

        self.channel_buttons = {}
        self.channel_badges = {}
        for ch in channels_list:
            ch_name = ch["name"]
            ch_topic = ch.get("topic", "")

            ch_row = ctk.CTkFrame(self.channels_scroll, fg_color="transparent", height=34)
            ch_row.pack(fill="x", pady=2)

            btn = ctk.CTkButton(
                ch_row,
                text=f"#  {ch_name}",
                anchor="w",
                font=("Segoe UI", 13),
                height=34,
                fg_color="transparent",
                hover_color=Colors.BG_MAIN,
                text_color=Colors.TEXT_SECONDARY,
                corner_radius=6,
                command=lambda cid=server_id, cname=ch_name, ctop=ch_topic: self._on_channel_click(cid, cname, ctop)
            )
            btn.pack(side="left", fill="both", expand=True)

            badge_frame = ctk.CTkFrame(
                ch_row,
                fg_color=Colors.ERROR,
                corner_radius=9,
                height=18
            )
            badge_lbl = ctk.CTkLabel(
                badge_frame,
                text="",
                font=("Segoe UI", 9, "bold"),
                text_color="#ffffff",
                padx=5
            )
            badge_lbl.pack(fill="both", expand=True)

            self.channel_buttons[ch_name] = btn
            self.channel_badges[ch_name] = (badge_frame, badge_lbl)

    def update_dm_badge(self, name: str, count: int):
        """Aktualizuje odznakę nieprzeczytanych wiadomości dla rozmówcy DM"""
        if not hasattr(self, "dm_badges") or name not in self.dm_badges:
            return
        badge_frame, badge_lbl = self.dm_badges[name]
        if count > 0:
            badge_lbl.configure(text=str(count) if count < 100 else "99+")
            badge_frame.pack(side="right", padx=(0, 8))
        else:
            badge_frame.pack_forget()

    def update_channel_badge(self, channel_name: str, count: int):
        """Aktualizuje odznakę nieprzeczytanych wiadomości dla kanału serwera"""
        if not hasattr(self, "channel_badges") or channel_name not in self.channel_badges:
            return
        badge_frame, badge_lbl = self.channel_badges[channel_name]
        if count > 0:
            badge_lbl.configure(text=str(count) if count < 100 else "99+")
            badge_frame.pack(side="right", padx=(0, 6))
        else:
            badge_frame.pack_forget()

    def update_server_badge(self, server_id, count: int):
        """Aktualizuje odznakę nieprzeczytanych wiadomości na ikonie serwera lub DMs"""
        key = server_id if server_id is not None else "dms"
        if not hasattr(self, "server_badges") or key not in self.server_badges:
            return
        badge_frame, badge_lbl = self.server_badges[key]
        if count > 0:
            badge_lbl.configure(text=str(count) if count < 100 else "99+")
            badge_frame.place(relx=0.88, rely=0.15, anchor="center")
            badge_frame.lift()
        else:
            badge_frame.place_forget()

    def show_in_app_toast(self, title: str, message: str, duration_ms: int = 4000):
        """Wyświetla elegancki toast in-app w prawym górnym rogu ekranu"""
        if hasattr(self, "_toast_frame") and self._toast_frame:
            try:
                self._toast_frame.destroy()
            except Exception:
                pass

        self._toast_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SIDEBAR,
            border_color=Colors.BUTTON_PRIMARY,
            border_width=1,
            corner_radius=10,
            width=320,
            height=60
        )
        self._toast_frame.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(
            self._toast_frame,
            text="🔔",
            font=("Segoe UI", 18),
            width=30
        )
        icon_lbl.pack(side="left", padx=(10, 6))

        text_box = ctk.CTkFrame(self._toast_frame, fg_color="transparent")
        text_box.pack(side="left", fill="both", expand=True, pady=6)

        t_lbl = ctk.CTkLabel(
            text_box,
            text=title,
            font=("Segoe UI", 12, "bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        )
        t_lbl.pack(fill="x")

        preview = message[:40] + ("..." if len(message) > 40 else "")
        m_lbl = ctk.CTkLabel(
            text_box,
            text=preview,
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        )
        m_lbl.pack(fill="x")

        self._toast_frame.place(relx=0.82, rely=0.07, anchor="center")
        self._toast_frame.lift()

        def _dismiss(e=None):
            if hasattr(self, "_toast_frame") and self._toast_frame:
                try:
                    self._toast_frame.place_forget()
                    self._toast_frame.destroy()
                    self._toast_frame = None
                except Exception:
                    pass

        self._toast_frame.bind("<Button-1>", _dismiss)
        icon_lbl.bind("<Button-1>", _dismiss)
        text_box.bind("<Button-1>", _dismiss)
        t_lbl.bind("<Button-1>", _dismiss)
        m_lbl.bind("<Button-1>", _dismiss)

        self.after(duration_ms, _dismiss)

    def highlight_active_channel(self, channel_name: str):
        """Wyróżnia aktywny kanał tekstowy na liście kanałów"""
        if not hasattr(self, 'channel_buttons'):
            return
        for cname, btn in self.channel_buttons.items():
            if cname == channel_name:
                btn.configure(fg_color=Colors.BG_MAIN, text_color=Colors.TEXT_PRIMARY)
            else:
                btn.configure(fg_color="transparent", text_color=Colors.TEXT_SECONDARY)

    def show_dms_sidebar(self):
        """Przełącza środkowy panel z powrotem na wiadomości prywatne (Znajomi)"""
        self.server_name_label.configure(text="🏠 Znajomi")
        self.server_channels_panel.pack_forget()
        self.dms_panel.pack(fill="both", expand=True)

    def show_create_server_modal(self, callback):
        """Otwiera okno modalne tworzenia nowego serwera"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Stwórz serwer")
        dialog.geometry("380x320")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Stwórz własny serwer",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            dialog,
            text="Twój serwer to przestrzeń do rozmów i gier ze znajomymi.",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY
        ).pack(pady=(0, 16))

        ctk.CTkLabel(dialog, text="NAZWA SERWERA", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=30)
        name_entry = ctk.CTkEntry(dialog, placeholder_text="np. Społeczność Python", font=Fonts.INPUT)
        name_entry.pack(fill="x", padx=30, pady=(4, 12))
        name_entry.focus()

        ctk.CTkLabel(dialog, text="WYBIERZ IKONĘ", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=30)
        icon_var = ctk.StringVar(value="🚀")
        icon_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        icon_frame.pack(fill="x", padx=30, pady=(4, 20))

        emojis = ["🚀", "🎮", "💻", "🎵", "🎨", "⚔️", "🛡️", "🌐"]
        for em in emojis:
            ctk.CTkRadioButton(
                icon_frame,
                text=em,
                value=em,
                variable=icon_var,
                width=34,
                font=("Segoe UI", 16)
            ).pack(side="left", padx=1)

        def _submit():
            s_name = name_entry.get().strip()
            if s_name:
                dialog.destroy()
                callback(s_name, icon_var.get())

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=30)

        ctk.CTkButton(btn_box, text="Anuluj", fg_color="transparent", hover_color=Colors.BG_MAIN, width=100, command=dialog.destroy).pack(side="left")
        ctk.CTkButton(btn_box, text="Utwórz", fg_color=Colors.BUTTON_PRIMARY, hover_color=Colors.BUTTON_PRIMARY_HOVER, width=120, command=_submit).pack(side="right")
        name_entry.bind("<Return>", lambda e: _submit())

    def show_manage_members_modal(
        self,
        server_name: str,
        members: list,
        available_users: list,
        add_callback,
        role_callback,
        remove_callback
    ) -> None:
        """Opens a modal for assigning roles and managing server membership."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Członkowie serwera")
        dialog.geometry("520x460")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f"Członkowie: {server_name}",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(16, 10))

        add_frame = ctk.CTkFrame(dialog, fg_color=Colors.BG_RIGHT)
        add_frame.pack(fill="x", padx=20, pady=(0, 10))

        user_names = {
            f"{u['username']} ({u['email']})": u["id"]
            for u in available_users
        }
        user_var = ctk.StringVar(value=next(iter(user_names), "Brak dostępnych użytkowników"))
        role_var = ctk.StringVar(value="member")

        ctk.CTkComboBox(
            add_frame,
            values=list(user_names) or ["Brak dostępnych użytkowników"],
            variable=user_var,
            state="readonly",
            width=260
        ).pack(side="left", padx=(8, 6), pady=8)
        ctk.CTkComboBox(
            add_frame,
            values=["member", "moderator", "admin"],
            variable=role_var,
            state="readonly",
            width=100
        ).pack(side="left", padx=4)

        def _add_member():
            user_id = user_names.get(user_var.get())
            if user_id is not None:
                add_callback(user_id, role_var.get())
                dialog.destroy()

        ctk.CTkButton(
            add_frame,
            text="Dodaj",
            width=70,
            command=_add_member
        ).pack(side="right", padx=8)

        scroll = ctk.CTkScrollableFrame(
            dialog,
            fg_color="transparent",
            height=300
        )
        scroll.pack(fill="both", expand=True, padx=20, pady=(4, 10))

        for member in members:
            if member["role"] == "owner":
                continue
            row = ctk.CTkFrame(scroll, fg_color=Colors.BG_RIGHT)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row,
                text=f"{member['username']}  •  {member['email']}",
                anchor="w",
                text_color=Colors.TEXT_PRIMARY
            ).pack(side="left", padx=8, fill="x", expand=True)

            role_choice = ctk.StringVar(value=member["role"])
            ctk.CTkComboBox(
                row,
                values=["member", "moderator", "admin"],
                variable=role_choice,
                state="readonly",
                width=110,
                command=lambda value, uid=member["user_id"]: role_callback(uid, value)
            ).pack(side="right", padx=(4, 4), pady=6)
            ctk.CTkButton(
                row,
                text="Usuń",
                width=58,
                fg_color=Colors.DND,
                hover_color=Colors.ERROR,
                command=lambda uid=member["user_id"]: (remove_callback(uid), dialog.destroy())
            ).pack(side="right", padx=(4, 8), pady=6)

        ctk.CTkButton(
            dialog,
            text="Zamknij",
            fg_color="transparent",
            width=100,
            command=dialog.destroy
        ).pack(pady=(0, 12))

    def show_create_channel_modal(self, server_name: str, callback):
        """Otwiera okno modalne tworzenia nowego kanału tekstowego"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Utwórz kanał")
        dialog.geometry("380x280")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f"Utwórz kanał w {server_name}",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(20, 4))

        ctk.CTkLabel(dialog, text="NAZWA KANAŁU", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=30)
        name_entry = ctk.CTkEntry(dialog, placeholder_text="np. dyskusje", font=Fonts.INPUT)
        name_entry.pack(fill="x", padx=30, pady=(4, 12))
        name_entry.focus()

        ctk.CTkLabel(dialog, text="TEMAT KANAŁU (OPCJONALNY)", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=30)
        topic_entry = ctk.CTkEntry(dialog, placeholder_text="O czym rozmawiamy na tym kanale?", font=Fonts.INPUT)
        topic_entry.pack(fill="x", padx=30, pady=(4, 20))

        def _submit():
            c_name = name_entry.get().strip()
            c_topic = topic_entry.get().strip()
            if c_name:
                dialog.destroy()
                callback(c_name, c_topic)

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=30)

        ctk.CTkButton(btn_box, text="Anuluj", fg_color="transparent", hover_color=Colors.BG_MAIN, width=100, command=dialog.destroy).pack(side="left")
        ctk.CTkButton(btn_box, text="Utwórz", fg_color=Colors.BUTTON_PRIMARY, hover_color=Colors.BUTTON_PRIMARY_HOVER, width=120, command=_submit).pack(side="right")
        name_entry.bind("<Return>", lambda e: _submit())

    def clear_message_input(self):
        """Czyści pole tekstowe wiadomości"""
        self.message_entry.delete(0, "end")

    def add_message(
        self,
        sender: str,
        text: str,
        is_own: bool = False,
        timestamp: str = "",
        is_bot: bool = False,
        attachments: list | None = None,
        reactions: list | None = None,
        message_id: int | None = None
    ):
        """Dodaje nową wiadomość do wirtualizowanego czatu (O(1))"""
        self.virtual_chat.add_message(
            sender=sender,
            content=text,
            is_own=is_own,
            timestamp=timestamp,
            is_bot=is_bot or ("Bot" in sender),
            attachments=attachments,
            reactions=reactions,
            message_id=message_id
        )

    def load_message_history(self, messages_data: list):
        """Ładuje historię wiadomości do wirtualnego widoku"""
        self.virtual_chat.set_messages(messages_data)

    def clear_chat_messages(self):
        """Czyści widok wiadomości"""
        self.virtual_chat.clear()

    def show_emoji_picker(self, callback) -> None:
        """Shows a compact emoji picker and delegates the selected emoji."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Emoji")
        dialog.geometry("300x170")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Wybierz emoji",
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(12, 8))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(padx=12, pady=8)
        emojis = ["😀", "😂", "😍", "👍", "👎", "🎉", "❤️", "🔥", "🚀", "🎮", "💻", "🎨"]

        def _choose(emoji: str) -> None:
            dialog.destroy()
            callback(emoji)

        for index, emoji in enumerate(emojis):
            ctk.CTkButton(
                frame,
                text=emoji,
                width=42,
                height=36,
                fg_color=Colors.BG_RIGHT,
                hover_color=Colors.BUTTON_PRIMARY,
                font=("Segoe UI", 17),
                command=lambda e=emoji: _choose(e)
            ).grid(row=index // 6, column=index % 6, padx=3, pady=3)

    def clear_history_search(self):
        """Clears all history-search fields."""
        if hasattr(self, "history_search_entry"):
            self.history_search_entry.delete(0, "end")
        if hasattr(self, "history_sender_entry"):
            self.history_sender_entry.delete(0, "end")
        if hasattr(self, "history_timestamp_entry"):
            self.history_timestamp_entry.delete(0, "end")

    def set_typing_indicator(self, text: str):
        """Ustawia sformatowany tekst wskaźnika pisania wielu użytkowników"""
        if hasattr(self, 'typing_label'):
            self.typing_label.configure(
                text=text,
                text_color=Colors.TEXT_PRIMARY if text else Colors.TEXT_SECONDARY
            )

    def update_network_status(self, text: str, color: str):
        """Aktualizuje badge połączenia w nagłówku"""
        if hasattr(self, 'net_status_label'):
            self.net_status_label.configure(text=text, text_color=color)

