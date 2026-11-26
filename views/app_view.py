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
        self._modal_backdrop = None
        self._active_popover = None
        self._popover_dismiss_bind_id = None

        # Konfiguracja grid - 3 kolumny (serwery | kanały | czat)
        self.grid_columnconfigure(0, weight=0, minsize=72)    # Serwery (stała szerokość)
        self.grid_columnconfigure(1, weight=0, minsize=240)   # Kanały/DMs (stała szerokość)
        self.grid_columnconfigure(2, weight=1, minsize=460)   # Czat (rozciągliwy)
        self.grid_rowconfigure(0, weight=1)

        # Utwórz sekcje
        self._create_servers_sidebar()
        self._create_channels_sidebar()
        self._create_chat_area()

    # ==========================================
    # IN-WINDOW MODALS & POPOVERS (SINGLE-WINDOW)
    # ==========================================

    def _close_in_window_modal(self) -> None:
        """Closes any active in-window modal overlay."""
        if getattr(self, "_modal_backdrop", None) is not None:
            try:
                self._modal_backdrop.destroy()
            except Exception:
                pass
            self._modal_backdrop = None

    def _close_in_window_popover(self) -> None:
        """Closes any active in-window popover or context menu."""
        if getattr(self, "_popover_dismiss_bind_id", None) is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._popover_dismiss_bind_id)
            except Exception:
                pass
            self._popover_dismiss_bind_id = None
        if getattr(self, "_active_popover", None) is not None:
            try:
                self._active_popover.destroy()
            except Exception:
                pass
            self._active_popover = None

    def _open_in_window_modal(self, title: str, width: int, height: int):
        """Creates a centered in-window modal overlay inside the main viewport."""
        self._close_in_window_modal()
        self._close_in_window_popover()

        backdrop = ctk.CTkFrame(
            self,
            fg_color="#111214",
            corner_radius=0
        )
        backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)
        backdrop.lift()
        self._modal_backdrop = backdrop

        vp_w = self.winfo_width() or 1080
        vp_h = self.winfo_height() or 720
        card_w = min(width, max(300, vp_w - 48))
        card_h = min(height, max(220, vp_h - 48))

        card = ctk.CTkFrame(
            backdrop,
            fg_color=Colors.BG_SECONDARY,
            border_color="#3f4147",
            border_width=1,
            corner_radius=12,
            width=card_w,
            height=card_h
        )
        card.pack_propagate(False)
        card.place(relx=0.5, rely=0.5, anchor="center")

        backdrop.bind("<Button-1>", lambda _e: self._close_in_window_modal())
        card.bind("<Button-1>", lambda _e: "break")

        header = ctk.CTkFrame(card, fg_color="transparent", height=40)
        header.pack(fill="x", padx=14, pady=(10, 4))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=title,
            font=Fonts.TITLE_SMALL,
            text_color=Colors.TEXT_PRIMARY,
            anchor="w"
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            header,
            text="✕",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            text_color=Colors.TEXT_SECONDARY,
            command=self._close_in_window_modal
        ).pack(side="right")

        try:
            self.winfo_toplevel().bind("<Escape>", lambda _e: self._close_in_window_modal(), add="+")
        except Exception:
            pass

        return card

    def _open_in_window_popover(self, width: int, height: int, x: int, y: int):
        """Creates an in-window floating popover/menu clamped to the viewport."""
        self._close_in_window_popover()

        vp_w = self.winfo_width() or 1080
        vp_h = self.winfo_height() or 720
        clamped_x = max(8, min(x, max(8, vp_w - width - 8)))
        clamped_y = max(8, min(y, max(8, vp_h - height - 8)))

        popover = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SIDEBAR,
            border_color="#3f4147",
            border_width=1,
            corner_radius=8,
            width=width,
            height=height
        )
        popover.pack_propagate(False)
        popover.place(x=clamped_x, y=clamped_y)
        popover.lift()
        self._active_popover = popover

        def _on_global_click(event):
            curr = event.widget
            while curr is not None:
                if curr == popover:
                    return
                curr = getattr(curr, "master", None)
            self._close_in_window_popover()

        try:
            root = self.winfo_toplevel()
            self._popover_dismiss_bind_id = root.bind("<Button-1>", _on_global_click, add="+")
            root.bind("<Escape>", lambda _e: self._close_in_window_popover(), add="+")
        except Exception:
            pass

        return popover

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

        if server_id not in (None, "add"):
            for target in (button_container, btn):
                target.bind(
                    "<Button-3>",
                    lambda e, sid=server_id, sname=tooltip: self._show_server_context_menu(e, sid, sname),
                    add="+"
                )

        return button_container

    def _show_server_context_menu(self, event, server_id: int, server_name: str) -> None:
        """Opens a Discord-style right-click context menu for a server icon."""
        rel_x = event.x_root - self.winfo_rootx() + 6
        rel_y = event.y_root - self.winfo_rooty()
        menu = self._open_in_window_popover(width=220, height=202, x=rel_x, y=rel_y)

        ctk.CTkLabel(
            menu,
            text=server_name[:24],
            font=("Segoe UI", 11, "bold"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        ).pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkFrame(menu, height=1, fg_color="#3f4147").pack(fill="x", padx=8, pady=(0, 4))

        def _run_action(action):
            self._close_in_window_popover()
            action()

        items = [
            ("🎨  Zarządzanie rolami", lambda: self.controller and self.controller.handle_role_settings_click(server_id)),
            ("👥  Członkowie serwera", lambda: self.controller and self.controller.handle_manage_members_click(server_id)),
            ("📊  Statystyki serwera", lambda: self.controller and self.controller.handle_analytics_click(server_id)),
        ]
        for label, cmd in items:
            ctk.CTkButton(
                menu,
                text=label,
                anchor="w",
                height=30,
                fg_color="transparent",
                hover_color=Colors.BUTTON_SECONDARY,
                text_color=Colors.TEXT_PRIMARY,
                font=("Segoe UI", 12),
                corner_radius=6,
                command=lambda c=cmd: _run_action(c)
            ).pack(fill="x", padx=6, pady=2)

        ctk.CTkFrame(menu, height=1, fg_color="#3f4147").pack(fill="x", padx=8, pady=4)

        ctk.CTkButton(
            menu,
            text="➕  Utwórz kanał",
            anchor="w",
            height=30,
            fg_color="transparent",
            hover_color=Colors.BUTTON_SECONDARY,
            text_color=Colors.TEXT_PRIMARY,
            font=("Segoe UI", 12),
            corner_radius=6,
            command=lambda: _run_action(
                lambda: self.controller and self.controller.handle_add_channel_click(server_id)
            )
        ).pack(fill="x", padx=6, pady=(0, 6))

    def _on_server_click(self, server_id, server_name):
        """Deleguje do controllera"""
        if self.controller:
            self.controller.handle_server_click(server_id, server_name)

    def _on_add_server_click(self):
        """Deleguje kliknięcie przycisku dodania serwera"""
        if self.controller:
            self.controller.handle_add_server_click()

    def _on_channel_click(self, server_id, channel_name, topic="", channel_type="text"):
        """Deleguje kliknięcie kanału tekstowego lub głosowego"""
        if self.controller:
            self.controller.handle_channel_click(
                server_id,
                channel_name,
                topic,
                channel_type
            )

    def _on_add_channel_click(self):
        """Deleguje kliknięcie przycisku dodania kanału"""
        if self.controller and hasattr(self, 'current_server_id'):
            self.controller.handle_add_channel_click(self.current_server_id)

    def _on_manage_members_click(self):
        """Delegates server member management to the controller."""
        if self.controller and hasattr(self, "current_server_id"):
            self.controller.handle_manage_members_click(self.current_server_id)

    def _on_analytics_click(self):
        """Delegates server analytics to the controller."""
        if self.controller and hasattr(self, "current_server_id"):
            self.controller.handle_analytics_click(self.current_server_id)

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

        channel_search_frame = ctk.CTkFrame(
            self.server_channels_panel,
            fg_color="transparent",
            height=40
        )
        channel_search_frame.pack(fill="x", padx=12, pady=(2, 4))
        channel_search_frame.pack_propagate(False)

        self.channel_search_entry = ctk.CTkEntry(
            channel_search_frame,
            placeholder_text="🔍 Szukaj kanału",
            height=30,
            fg_color=Colors.BG_MAIN,
            border_width=0,
            font=Fonts.INPUT
        )
        self.channel_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.channel_search_entry.bind("<KeyRelease>", self._on_channel_search)

        self.channel_sort_var = ctk.StringVar(value="position")
        self.channel_sort_combo = ctk.CTkComboBox(
            channel_search_frame,
            values=["position", "name", "name_desc", "topic"],
            variable=self.channel_sort_var,
            state="readonly",
            width=88,
            height=30,
            command=lambda _: self._on_channel_search()
        )
        self.channel_sort_combo.pack(side="right")
        ctk.CTkButton(
            channel_search_frame,
            text="⭐",
            width=32,
            height=30,
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            command=self._on_channel_bookmarks_click
        ).pack(side="right", padx=(0, 4))

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
        if not hasattr(self, "conversation_name_widgets"):
            self.conversation_name_widgets = {}
        self.conversation_name_widgets[name] = name_label

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

    def _on_channel_search(self, event=None):
        """Delegates channel filtering and sorting to the controller."""
        if not self.controller or not hasattr(self, "channel_search_entry"):
            return
        query = self.channel_search_entry.get()
        sort_by = self.channel_sort_var.get()
        self.controller.handle_channel_search(query, sort_by)

    def _on_channel_bookmarks_click(self):
        """Delegates bookmark panel display to the controller."""
        if self.controller:
            self.controller.handle_show_channel_bookmarks()

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
        """Wyświetla nakładkę wyboru statusu (Dostępny, Zaraz wracam, DND, Niewidoczny)"""
        dialog = self._open_in_window_modal("Ustaw status obecności", 420, 490)

        ctk.CTkLabel(
            dialog,
            text="Wybierz jak chcesz być widoczny dla znajomych.",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY
        ).pack(pady=(2, 12))

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
            self._close_in_window_modal()
            callback(sel_status, c_text)

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=24, pady=(4, 12))

        ctk.CTkButton(
            btn_box,
            text="Anuluj",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
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

        self.pinned_messages_button = ctk.CTkButton(
            chat_header,
            text="📌",
            width=36,
            height=30,
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            command=self._on_pinned_messages_click
        )
        self.pinned_messages_button.pack(side="right", padx=(4, 2))

        self.history_search_entry = ctk.CTkEntry(
            chat_header,
            placeholder_text="Szukaj w historii",
            placeholder_text_color="#949ba4",
            width=140,
            height=30,
            corner_radius=6,
            fg_color=Colors.BG_SIDEBAR,
            border_width=1,
            border_color="#3f4147",
            font=("Segoe UI", 12)
        )
        self.history_search_entry.pack(side="right", padx=(4, 4))
        self.history_search_entry.bind("<KeyRelease>", self._on_history_search)
        self.history_search_entry.bind("<FocusIn>", lambda _e: self.history_search_entry.configure(border_color="#5865f2"))
        self.history_search_entry.bind("<FocusOut>", lambda _e: self.history_search_entry.configure(border_color="#3f4147"))

        self.history_sender_entry = ctk.CTkEntry(
            chat_header,
            placeholder_text="Nadawca",
            placeholder_text_color="#949ba4",
            width=96,
            height=30,
            corner_radius=6,
            fg_color=Colors.BG_SIDEBAR,
            border_width=1,
            border_color="#3f4147",
            font=("Segoe UI", 12)
        )
        self.history_sender_entry.pack(side="right", padx=(4, 4))
        self.history_sender_entry.bind("<KeyRelease>", self._on_history_search)
        self.history_sender_entry.bind("<FocusIn>", lambda _e: self.history_sender_entry.configure(border_color="#5865f2"))
        self.history_sender_entry.bind("<FocusOut>", lambda _e: self.history_sender_entry.configure(border_color="#3f4147"))

        self.history_timestamp_entry = ctk.CTkEntry(
            chat_header,
            placeholder_text="Czas HH:MM",
            placeholder_text_color="#949ba4",
            width=88,
            height=30,
            corner_radius=6,
            fg_color=Colors.BG_SIDEBAR,
            border_width=1,
            border_color="#3f4147",
            font=("Segoe UI", 12)
        )
        self.history_timestamp_entry.pack(side="right", padx=(4, 4))
        self.history_timestamp_entry.bind("<KeyRelease>", self._on_history_search)
        self.history_timestamp_entry.bind("<FocusIn>", lambda _e: self.history_timestamp_entry.configure(border_color="#5865f2"))
        self.history_timestamp_entry.bind("<FocusOut>", lambda _e: self.history_timestamp_entry.configure(border_color="#3f4147"))

        # Wskaźnik stanu sieci i latencji (Discord-like connection badge)
        self.net_status_label = ctk.CTkLabel(
            chat_header,
            text="🟢 Połączono",
            font=("Segoe UI", 11),
            text_color=Colors.ONLINE
        )
        self.net_status_label.pack(side="right", padx=(6, 8))

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
            fg_color="transparent"
        )
        input_container.pack(fill="x", padx=16, pady=(0, 16))

        # Wskaźnik "pisze..." (typing indicator)
        self.typing_label = ctk.CTkLabel(
            input_container,
            text="",
            font=("Segoe UI", 11, "italic"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
            height=18
        )
        self.typing_label.pack(fill="x", padx=4, pady=(0, 2))

        self.reply_context_frame = ctk.CTkFrame(
            input_container,
            fg_color=Colors.BG_SECONDARY,
            border_color="#3f4147",
            border_width=1,
            height=32,
            corner_radius=6
        )
        self.reply_context_frame.pack_propagate(False)
        self.reply_context_label = ctk.CTkLabel(
            self.reply_context_frame,
            text="",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        )
        self.reply_context_label.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(
            self.reply_context_frame,
            text="×",
            width=28,
            height=26,
            fg_color="transparent",
            hover_color=Colors.BG_RIGHT,
            command=self._on_cancel_reply
        ).pack(side="right", padx=4)

        # Frame z inputem (jak Discord)
        self.input_frame = ctk.CTkFrame(
            input_container,
            fg_color=Colors.INPUT_BG,
            corner_radius=8,
            height=44
        )
        self.input_frame.pack(fill="x")
        self.input_frame.pack_propagate(False)
        input_frame = self.input_frame

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

    def _on_cancel_reply(self):
        """Cancels threaded reply composition."""
        if self.controller:
            self.controller.handle_cancel_reply()

    def set_reply_context(self, context: dict) -> None:
        """Shows the parent message above the composer."""
        sender = context.get("sender", "User")
        content = (context.get("content", "") or "").replace("\n", " ")
        if len(content) > 80:
            content = content[:77] + "..."
        self.reply_context_label.configure(text=f"↩ Odpowiedź dla {sender}: {content}")
        if not self.reply_context_frame.winfo_ismapped():
            self.reply_context_frame.pack(
                fill="x",
                padx=4,
                pady=(0, 4),
                before=self.input_frame
            )
        if hasattr(self, "message_entry"):
            self.message_entry.focus_set()

    def clear_reply_context(self) -> None:
        """Hides threaded reply context."""
        self.reply_context_label.configure(text="")
        self.reply_context_frame.pack_forget()

    def _on_pinned_messages_click(self):
        """Delegates pinned-message panel display to the controller."""
        if self.controller:
            self.controller.handle_show_pinned_messages()

    def _on_toggle_channel_bookmark(self, channel_id: int):
        """Toggles a channel bookmark."""
        if self.controller:
            self.controller.handle_toggle_channel_bookmark(channel_id)

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
            self.virtual_chat.set_react_prompt_callback(
                lambda message_id: controller.handle_message_react_prompt(message_id)
            )
            self.virtual_chat.set_pin_callback(
                lambda message_id: controller.handle_toggle_pin(message_id),
                enabled=True
            )
            self.virtual_chat.set_reply_callback(
                lambda message_id: controller.handle_reply_to_message(int(message_id))
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
        grouped = {}
        if getattr(self.controller, "server_model", None):
            try:
                grouped = self.controller.server_model.get_grouped_channels(server_id)
            except Exception:
                grouped = {}

        categories = []
        if grouped:
            for key, value in grouped.items():
                if key == "uncategorized":
                    continue
                categories.append(value)

        def render_channel(ch):
            ch_name = ch["name"]
            ch_topic = ch.get("topic", "")
            ch_type = ch.get("channel_type", "text")
            ch_icon = "🔊" if ch_type == "voice" else "#"

            ch_row = ctk.CTkFrame(self.channels_scroll, fg_color="transparent", height=34)
            ch_row.pack(fill="x", pady=2)

            btn = ctk.CTkButton(
                ch_row,
                text=f"{ch_icon}  {ch_name}",
                anchor="w",
                font=("Segoe UI", 13),
                height=34,
                fg_color="transparent",
                hover_color=Colors.BG_MAIN,
                text_color=Colors.TEXT_SECONDARY,
                corner_radius=6,
                command=lambda cid=server_id, cname=ch_name, ctop=ch_topic, ctype=ch_type: self._on_channel_click(cid, cname, ctop, ctype)
            )
            btn.pack(side="left", fill="both", expand=True)

            bookmark_btn = ctk.CTkButton(
                ch_row,
                text="☆",
                width=30,
                height=30,
                fg_color="transparent",
                hover_color=Colors.BG_MAIN,
                command=lambda cid=ch.get("id"): self._on_toggle_channel_bookmark(cid)
            )
            bookmark_btn.pack(side="right", padx=(2, 4))

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

        for category_value in categories:
            category = category_value["category"]
            category_channels = [
                ch for ch in category_value["channels"]
                if ch["id"] in {item["id"] for item in channels_list}
            ]
            if not category_channels:
                continue
            collapsed = bool(category["collapsed"])
            category_row = ctk.CTkFrame(
                self.channels_scroll,
                fg_color="transparent",
                height=28
            )
            category_row.pack(fill="x", pady=(6, 2))

            def toggle_category(cat_id=category["id"], cat=category):
                next_state = not bool(cat["collapsed"])
                cat["collapsed"] = next_state
                self.controller.server_model.set_category_collapsed(cat_id, next_state)
                self.show_server_channels(server_id, server_name, channels_list)

            ctk.CTkButton(
                category_row,
                text=f"{'▶' if collapsed else '▼'}  {category['name']}",
                anchor="w",
                height=28,
                fg_color="transparent",
                hover_color=Colors.BG_MAIN,
                text_color=Colors.TEXT_SECONDARY,
                command=toggle_category
            ).pack(fill="x")
            if not collapsed:
                for ch in category_channels:
                    render_channel(ch)

        uncategorized = [
            ch for ch in channels_list
            if ch.get("category_id") is None
        ]
        for ch in uncategorized:
            render_channel(ch)

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

        self._toast_frame.place(relx=1.0, x=-16, y=58, anchor="ne")
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
        """Otwiera nakładkę tworzenia nowego serwera"""
        dialog = self._open_in_window_modal("Stwórz własny serwer", 400, 320)

        ctk.CTkLabel(
            dialog,
            text="Twój serwer to przestrzeń do rozmów i gier ze znajomymi.",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_SECONDARY
        ).pack(pady=(2, 14))

        ctk.CTkLabel(dialog, text="NAZWA SERWERA", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=28)
        name_entry = ctk.CTkEntry(dialog, placeholder_text="np. Społeczność Python", font=Fonts.INPUT)
        name_entry.pack(fill="x", padx=28, pady=(4, 12))
        name_entry.focus()

        ctk.CTkLabel(dialog, text="WYBIERZ IKONĘ", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=28)
        icon_var = ctk.StringVar(value="🚀")
        icon_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        icon_frame.pack(fill="x", padx=28, pady=(4, 18))

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
                self._close_in_window_modal()
                callback(s_name, icon_var.get())

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=28)

        ctk.CTkButton(btn_box, text="Anuluj", fg_color="transparent", hover_color=Colors.BG_MAIN, width=100, command=self._close_in_window_modal).pack(side="left")
        ctk.CTkButton(btn_box, text="Utwórz", fg_color=Colors.BUTTON_PRIMARY, hover_color=Colors.BUTTON_PRIMARY_HOVER, width=120, command=_submit).pack(side="right")
        name_entry.bind("<Return>", lambda e: _submit())

    def show_role_settings_modal(
        self,
        roles: list,
        members: list,
        color_callback,
        rgb_callback,
        assign_callback
    ) -> None:
        """Opens the role color, RGB and assignment editor inside the main window."""
        dialog = self._open_in_window_modal("🎨 Role i kolory nicków", 620, 540)

        swatches = [
            "#ff3333", "#5865f2", "#23a55a", "#f0b232",
            "#a855f7", "#d946ef", "#00d9ff", "#b5bac1"
        ]
        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=320)
        scroll.pack(fill="both", expand=True, padx=18, pady=(4, 8))

        for role in roles:
            card = ctk.CTkFrame(scroll, fg_color=Colors.BG_RIGHT, corner_radius=8)
            card.pack(fill="x", pady=5)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 4))

            role_label = ctk.CTkLabel(
                top_row,
                text=f"{role['name']}  •  priorytet {role['priority']}",
                text_color=role["color"],
                font=Fonts.LABEL,
                anchor="w"
            )
            role_label.pack(side="left", fill="x", expand=True)

            hex_var = ctk.StringVar(value=role["color"])

            def _apply_color(r_name=role["name"], col=None, lbl=role_label, hv=hex_var):
                chosen = col if col is not None else hv.get().strip()
                hv.set(chosen)
                try:
                    lbl.configure(text_color=chosen)
                except Exception:
                    pass
                color_callback(r_name, chosen)

            ctk.CTkEntry(
                top_row,
                textvariable=hex_var,
                width=82,
                height=28
            ).pack(side="left", padx=4)
            ctk.CTkButton(
                top_row,
                text="Zapisz",
                width=64,
                height=28,
                command=lambda fn=_apply_color: fn()
            ).pack(side="left", padx=(2, 0))

            bottom_row = ctk.CTkFrame(card, fg_color="transparent")
            bottom_row.pack(fill="x", padx=10, pady=(2, 8))

            for swatch in swatches:
                ctk.CTkButton(
                    bottom_row,
                    text="",
                    width=24,
                    height=24,
                    fg_color=swatch,
                    hover_color=swatch,
                    border_width=0,
                    command=lambda c=swatch, fn=_apply_color: fn(col=c)
                ).pack(side="left", padx=2)

            interval_var = ctk.StringVar(
                value=str(role["rgb_interval_ms"])
            )
            rgb_var = ctk.BooleanVar(value=role["is_rgb"])
            ctk.CTkComboBox(
                bottom_row,
                values=["5000", "10000"],
                variable=interval_var,
                state="readonly",
                width=82,
                height=26,
                command=lambda value, r=role["name"], rv=rgb_var:
                    rgb_callback(r, rv.get(), int(value))
            ).pack(side="right", padx=(4, 0))
            ctk.CTkSwitch(
                bottom_row,
                text="RGB",
                variable=rgb_var,
                command=lambda r=role["name"], rv=rgb_var, iv=interval_var:
                    rgb_callback(r, rv.get(), int(iv.get()))
            ).pack(side="right", padx=6)

        assign_frame = ctk.CTkFrame(dialog, fg_color=Colors.BG_RIGHT, corner_radius=8)
        assign_frame.pack(fill="x", padx=18, pady=(0, 8))
        member_names = {
            f"{member['username']} ({member['email']})": member["user_id"]
            for member in members
        }
        member_var = ctk.StringVar(value=next(iter(member_names), "Brak członków"))
        role_var = ctk.StringVar(value="member")
        ctk.CTkComboBox(
            assign_frame,
            values=list(member_names) or ["Brak członków"],
            variable=member_var,
            state="readonly",
            width=240
        ).pack(side="left", padx=8, pady=8)
        ctk.CTkComboBox(
            assign_frame,
            values=["member", "moderator", "admin"],
            variable=role_var,
            state="readonly",
            width=110
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            assign_frame,
            text="Przypisz",
            width=80,
            command=lambda: assign_callback(
                member_names.get(member_var.get()),
                role_var.get()
            )
        ).pack(side="right", padx=8)

        ctk.CTkButton(
            dialog,
            text="Zamknij",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
        ).pack(pady=(0, 12))

    def show_manage_members_modal(
        self,
        server_name: str,
        members: list,
        available_users: list,
        add_callback,
        role_callback,
        remove_callback,
        activity_callback=None
    ) -> None:
        """Opens an in-window modal for assigning roles and managing server membership."""
        dialog = self._open_in_window_modal(f"Członkowie: {server_name}", 540, 470)

        add_frame = ctk.CTkFrame(dialog, fg_color=Colors.BG_RIGHT, corner_radius=8)
        add_frame.pack(fill="x", padx=18, pady=(4, 10))

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

        ctk.CTkButton(
            add_frame,
            text="Dodaj",
            width=70,
            command=_add_member
        ).pack(side="right", padx=8)

        scroll = ctk.CTkScrollableFrame(
            dialog,
            fg_color="transparent",
            height=290
        )
        scroll.pack(fill="both", expand=True, padx=18, pady=(4, 10))

        for member in members:
            if member["role"] == "owner":
                continue
            row = ctk.CTkFrame(scroll, fg_color=Colors.BG_RIGHT, corner_radius=8)
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
                command=lambda uid=member["user_id"]: remove_callback(uid)
            ).pack(side="right", padx=(4, 8), pady=6)

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(pady=(0, 12))
        if activity_callback:
            ctk.CTkButton(
                footer,
                text="Historia",
                width=100,
                fg_color=Colors.BG_RIGHT,
                command=activity_callback
            ).pack(side="left", padx=6)
        ctk.CTkButton(
            footer,
            text="Zamknij",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
        ).pack(side="left", padx=6)

    def show_server_analytics_modal(self, analytics: dict) -> None:
        """Shows aggregate server metrics in an in-window modal."""
        dialog = self._open_in_window_modal(
            f"📊 {analytics.get('server_name', 'Serwer')}",
            540,
            350
        )

        grid = ctk.CTkFrame(dialog, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=(8, 0))
        cards = [
            ("Członkowie", analytics.get("member_count", 0)),
            ("Kanały", analytics.get("channel_count", 0)),
            ("Wiadomości", analytics.get("message_count", 0)),
            ("Zdarzenia", analytics.get("activity_count", 0))
        ]
        for index, (label, value) in enumerate(cards):
            card = ctk.CTkFrame(grid, fg_color=Colors.BG_RIGHT, corner_radius=8)
            card.grid(row=0, column=index, padx=5, sticky="nsew")
            grid.grid_columnconfigure(index, weight=1)
            ctk.CTkLabel(
                card,
                text=str(value),
                font=("Segoe UI", 22, "bold"),
                text_color=Colors.BUTTON_PRIMARY
            ).pack(pady=(12, 2))
            ctk.CTkLabel(
                card,
                text=label,
                text_color=Colors.TEXT_SECONDARY
            ).pack(pady=(0, 12))

        role_counts = analytics.get("role_counts", {})
        role_frame = ctk.CTkFrame(dialog, fg_color=Colors.BG_RIGHT, corner_radius=8)
        role_frame.pack(fill="x", padx=20, pady=18)
        ctk.CTkLabel(
            role_frame,
            text="Role członków",
            font=Fonts.LABEL,
            text_color=Colors.TEXT_PRIMARY
        ).pack(anchor="w", padx=12, pady=(10, 4))
        role_text = "  •  ".join(
            f"{role}: {count}"
            for role, count in sorted(role_counts.items())
        ) or "Brak członków"
        ctk.CTkLabel(
            role_frame,
            text=role_text,
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        ).pack(anchor="w", padx=12, pady=(0, 12))

        ctk.CTkButton(
            dialog,
            text="Zamknij",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
        ).pack(pady=(0, 12))

    def show_activity_logs_modal(self, server_name: str, logs: list) -> None:
        """Shows a read-only member activity log in-window modal."""
        dialog = self._open_in_window_modal(f"Historia aktywności: {server_name}", 620, 430)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=310)
        scroll.pack(fill="both", expand=True, padx=18, pady=(4, 10))
        if not logs:
            ctk.CTkLabel(
                scroll,
                text="Brak zapisów aktywności.",
                text_color=Colors.TEXT_SECONDARY
            ).pack(pady=20)
        for entry in logs:
            actor = entry.get("actor_name") or "System"
            target = entry.get("target_name") or "—"
            action = entry.get("action", "")
            details = entry.get("details", "")
            ctk.CTkLabel(
                scroll,
                text=f"{entry.get('created_at', '')}  •  {actor}  →  {target}\n{action}: {details}",
                anchor="w",
                justify="left",
                wraplength=540,
                text_color=Colors.TEXT_PRIMARY,
                fg_color=Colors.BG_RIGHT,
                corner_radius=6
            ).pack(fill="x", pady=3, padx=4)

        ctk.CTkButton(
            dialog,
            text="Zamknij",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
        ).pack(pady=(0, 12))

    def show_create_channel_modal(self, server_name: str, callback):
        """Otwiera nakładkę tworzenia nowego kanału tekstowego"""
        dialog = self._open_in_window_modal(f"Utwórz kanał w {server_name}", 400, 270)

        ctk.CTkLabel(dialog, text="NAZWA KANAŁU", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=28, pady=(8, 0))
        name_entry = ctk.CTkEntry(dialog, placeholder_text="np. dyskusje", font=Fonts.INPUT)
        name_entry.pack(fill="x", padx=28, pady=(4, 12))
        name_entry.focus()

        ctk.CTkLabel(dialog, text="TEMAT KANAŁU (OPCJONALNY)", font=("Segoe UI", 11, "bold"), text_color=Colors.TEXT_SECONDARY, anchor="w").pack(fill="x", padx=28)
        topic_entry = ctk.CTkEntry(dialog, placeholder_text="O czym rozmawiamy na tym kanale?", font=Fonts.INPUT)
        topic_entry.pack(fill="x", padx=28, pady=(4, 18))

        def _submit():
            c_name = name_entry.get().strip()
            c_topic = topic_entry.get().strip()
            if c_name:
                self._close_in_window_modal()
                callback(c_name, c_topic)

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=28)

        ctk.CTkButton(btn_box, text="Anuluj", fg_color="transparent", hover_color=Colors.BG_MAIN, width=100, command=self._close_in_window_modal).pack(side="left")
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
        message_id: int | None = None,
        nickname_color: str = "",
        reply_context: dict | None = None
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
            message_id=message_id,
            nickname_color=nickname_color,
            reply_context=reply_context
        )

    def load_message_history(self, messages_data: list):
        """Ładuje historię wiadomości do wirtualnego widoku"""
        self.virtual_chat.set_messages(messages_data)

    def clear_chat_messages(self):
        """Czyści widok wiadomości"""
        self.virtual_chat.clear()

    def show_emoji_picker(self, callback) -> None:
        """Shows an in-window emoji picker popover and delegates the selected emoji."""
        vp_w = self.winfo_width() or 1080
        vp_h = self.winfo_height() or 720
        popover = self._open_in_window_popover(
            width=292,
            height=138,
            x=vp_w - 312,
            y=vp_h - 210
        )

        ctk.CTkLabel(
            popover,
            text="Wybierz emoji",
            font=("Segoe UI", 12, "bold"),
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(8, 4))

        frame = ctk.CTkFrame(popover, fg_color="transparent")
        frame.pack(padx=10, pady=4)
        emojis = ["😀", "😂", "😍", "👍", "👎", "🎉", "❤️", "🔥", "🚀", "🎮", "💻", "🎨"]

        def _choose(emoji: str) -> None:
            self._close_in_window_popover()
            callback(emoji)

        for index, emoji in enumerate(emojis):
            ctk.CTkButton(
                frame,
                text=emoji,
                width=40,
                height=34,
                fg_color=Colors.BG_RIGHT,
                hover_color=Colors.BUTTON_SECONDARY,
                font=("Segoe UI", 17),
                command=lambda e=emoji: _choose(e)
            ).grid(row=index // 6, column=index % 6, padx=3, pady=3)

    def show_channel_bookmarks_modal(self, bookmarks: list) -> None:
        """Shows and allows quick access to bookmarked channels in an in-window modal."""
        dialog = self._open_in_window_modal("⭐ Zakładki kanałów", 460, 380)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=260)
        scroll.pack(fill="both", expand=True, padx=18, pady=(4, 10))
        if not bookmarks:
            ctk.CTkLabel(
                scroll,
                text="Brak zapisanych kanałów.",
                text_color=Colors.TEXT_SECONDARY
            ).pack(pady=20)

        for bookmark in bookmarks:
            server_name = bookmark["server_name"]
            channel_name = bookmark["channel_name"]
            channel_type = bookmark["channel_type"]
            icon = "🔊" if channel_type == "voice" else "#"
            row = ctk.CTkFrame(scroll, fg_color=Colors.BG_RIGHT, corner_radius=8)
            row.pack(fill="x", pady=3)

            def open_bookmark(
                sid=bookmark["server_id"],
                sname=server_name,
                cname=channel_name,
                ctype=channel_type
            ):
                self._close_in_window_modal()
                if self.controller:
                    self.controller.handle_server_click(sid, sname)
                    self.controller.handle_channel_click(
                        sid,
                        cname,
                        "",
                        ctype
                    )

            ctk.CTkButton(
                row,
                text=f"⭐ {icon}  {server_name} / {channel_name}",
                anchor="w",
                fg_color="transparent",
                hover_color=Colors.BG_MAIN,
                command=open_bookmark
            ).pack(side="left", fill="x", expand=True, padx=8, pady=8)

        ctk.CTkButton(
            dialog,
            text="Zamknij",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
        ).pack(pady=(0, 12))

    def show_thread_modal(self, root_message_id: int, replies: list) -> None:
        """Shows direct threaded replies for a message in an in-window modal."""
        dialog = self._open_in_window_modal(f"↩ Wątek wiadomości #{root_message_id}", 520, 420)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=300)
        scroll.pack(fill="both", expand=True, padx=18, pady=(4, 10))
        if not replies:
            ctk.CTkLabel(
                scroll,
                text="Brak odpowiedzi w tym wątku.",
                text_color=Colors.TEXT_SECONDARY
            ).pack(pady=20)

        for reply in replies:
            card = ctk.CTkFrame(scroll, fg_color=Colors.BG_RIGHT, corner_radius=8)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(
                card,
                text=f"{reply.get('sender', 'User')} • {reply.get('timestamp', '')}",
                font=Fonts.LABEL,
                text_color=Colors.TEXT_PRIMARY,
                anchor="w"
            ).pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                card,
                text=reply.get("content", ""),
                text_color=Colors.TEXT_INPUT,
                anchor="w",
                justify="left",
                wraplength=440
            ).pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkButton(
            dialog,
            text="Zamknij",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
        ).pack(pady=(0, 12))

    def show_pinned_messages_modal(self, pinned_messages: list) -> None:
        """Shows pinned messages for the active conversation in an in-window modal."""
        dialog = self._open_in_window_modal("📌 Przypięte wiadomości", 520, 420)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=300)
        scroll.pack(fill="both", expand=True, padx=18, pady=(4, 10))
        if not pinned_messages:
            ctk.CTkLabel(
                scroll,
                text="Brak przypiętych wiadomości.",
                text_color=Colors.TEXT_SECONDARY
            ).pack(pady=20)

        for item in pinned_messages:
            card = ctk.CTkFrame(scroll, fg_color=Colors.BG_RIGHT, corner_radius=8)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(
                card,
                text=f"{item.get('sender', 'User')} • {item.get('timestamp', '')}",
                font=Fonts.LABEL,
                text_color=Colors.TEXT_PRIMARY,
                anchor="w"
            ).pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                card,
                text=item.get("content", ""),
                text_color=Colors.TEXT_INPUT,
                justify="left",
                anchor="w",
                wraplength=440
            ).pack(fill="x", padx=10, pady=(0, 6))
            ctk.CTkLabel(
                card,
                text=f"Przypiął: {item.get('pinned_by', 'User')} • {item.get('pinned_at', '')}",
                font=("Segoe UI", 10),
                text_color=Colors.TEXT_SECONDARY,
                anchor="w"
            ).pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkButton(
            dialog,
            text="Zamknij",
            fg_color="transparent",
            hover_color=Colors.BG_MAIN,
            width=100,
            command=self._close_in_window_modal
        ).pack(pady=(0, 12))

    def show_voice_status(self, channel_name: str, participants: list) -> None:
        """Shows mock voice-channel connection status."""
        if not hasattr(self, "_voice_status_frame"):
            self._voice_status_frame = ctk.CTkFrame(
                self.channels_frame,
                fg_color=Colors.BG_MAIN,
                corner_radius=8
            )
        self._voice_status_frame.pack(fill="x", padx=12, pady=(0, 8), side="bottom")
        for child in self._voice_status_frame.winfo_children():
            child.destroy()

        ctk.CTkLabel(
            self._voice_status_frame,
            text=f"🔊 Połączono: {channel_name}",
            font=("Segoe UI", 11, "bold"),
            text_color=Colors.ONLINE,
            anchor="w"
        ).pack(fill="x", padx=10, pady=(8, 2))

        names = ", ".join(
            f"{item['user_name']}{' 🔇' if item['muted'] else ''}"
            for item in participants
        ) or "Brak uczestników"
        ctk.CTkLabel(
            self._voice_status_frame,
            text=names,
            text_color=Colors.TEXT_SECONDARY,
            anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 6))

        actions = ctk.CTkFrame(self._voice_status_frame, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(
            actions,
            text="🎙",
            width=44,
            command=lambda: self.controller.handle_voice_mute_toggle()
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            actions,
            text="Rozłącz",
            width=90,
            fg_color=Colors.DND,
            hover_color=Colors.ERROR,
            command=lambda: self.controller.handle_voice_channel_leave()
        ).pack(side="right", padx=4)

    def clear_voice_status(self) -> None:
        """Clears mock voice-channel status."""
        if hasattr(self, "_voice_status_frame") and self._voice_status_frame:
            self._voice_status_frame.pack_forget()

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

