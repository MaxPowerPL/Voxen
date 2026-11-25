"""
CONTROLLER - Obsługa logiki głównego ekranu aplikacji, serwerów, kanałów, silnika sieciowego i SQLite
"""

import time
from tkinter import filedialog
from typing import Any, Dict, Optional
from models.chat_model import ChatModel
from models.presence_tracker import PresenceTracker
from models.server_model import ServerModel
from models.typing_tracker import TypingTracker
from network.connection import ConnectionState
from network.protocol import Packet, PacketType
from notifications.notifier import WindowsNotifier
from storage.file_manager import FileManager
from utils import Colors


class AppController:
    """Controller głównego ekranu aplikacji (Controller w MVC)"""

    def __init__(self, model, view, app):
        """
        Inicjalizacja controllera

        Args:
            model: Model danych aplikacji
            view: Instancja AppView
            app: Instancja głównej aplikacji App (zawierająca network_client)
        """
        self.model = model
        self.view = view
        self.app = app

        # Stan serwerów i kanałów
        self.current_server = "Direct Messages"
        self.current_server_id: Optional[int] = None
        self.current_channel: Optional[str] = None
        self.current_conversation = "Unity Bot"
        self.current_tab = "Znajomi"

        # Dane zalogowanego użytkownika
        self.current_user = getattr(app, "current_user", {})
        self.sender_name = self.current_user.get("username") or self.current_user.get("email", "User").split("@")[0]

        # Modele
        self.chat_model = ChatModel(db_path="voxen.db")
        self.server_model = ServerModel(db_path="voxen.db")
        self.typing_tracker = TypingTracker(default_expiry=4.5)
        self.presence_tracker = PresenceTracker()
        self.db = getattr(self.chat_model, "db", None)
        self.file_manager = FileManager()

        # Pobierz zapisany status obecności z SQLite
        uid = self.current_user.get("id") or self.current_user.get("email", "")
        saved_st = self.db.get_user_status(uid) if self.db else {"status": "online", "custom_status": ""}
        self.my_status = saved_st.get("status", "online")
        self.my_custom_status = saved_st.get("custom_status", "")

        # Stan pisania użytkownika lokalnego (throttling & debounce)
        self._last_typing_sent: float = 0.0
        self._typing_stop_timer = None

        # Natywny system powiadomień Windows i in-app toast
        self.notifier = WindowsNotifier()
        self.notifier.add_listener(self._on_in_app_notification)
        if self.my_status == "dnd":
            self.notifier.set_dnd_mode(True)

        # Ustaw początkowy status w UI
        if hasattr(self.view, "update_my_status"):
            self.view.update_my_status(self.my_status, self.my_custom_status)

        # Podłączenie silnika sieciowego
        self.network = getattr(app, "network_client", None)
        if self.network:
            self._setup_network_bindings()

        # Załaduj dynamiczną listę serwerów z SQLite
        self.load_servers()

        # Załaduj początkową historię wiadomości
        self.chat_model.mark_as_read(self.current_conversation, self.sender_name)
        self._load_conversation_history(self.current_conversation)

        # Inicjalizacja odznak nieprzeczytanych wiadomości
        self._update_all_badges()

        # Uruchomienie cyklicznego sprawdzania wygasania wskaźników pisania (auto-decay)
        self._schedule_typing_decay()

    def _schedule_typing_decay(self):
        """Okresowo sprawdza i usuwa przedawnione wskaźniki pisania"""
        if hasattr(self.view, "after"):
            try:
                self.view.after(1000, self._on_typing_decay_tick)
            except Exception:
                pass

    def _on_typing_decay_tick(self):
        """Tick pętli decay dla wskaźników pisania"""
        changed = self.typing_tracker.clean_expired()
        if changed:
            self._refresh_typing_indicator()
        self._schedule_typing_decay()

    def _refresh_typing_indicator(self):
        """Odświeża tekst wskaźnika pisania dla aktywnej konwersacji"""
        text = self.typing_tracker.format_typing_text(self.current_conversation)
        self.view.set_typing_indicator(text)

    def _on_in_app_notification(self, title: str, message: str):
        """Wyświetla banner powiadomienia w wątku UI"""
        try:
            if hasattr(self.view, "after"):
                self.view.after(0, lambda: self.view.show_in_app_toast(title, message))
        except Exception:
            pass

    def load_servers(self):
        """Pobiera serwery z bazy SQLite i zleca renderowanie w lewej kolumnie"""
        servers = self.server_model.get_all_servers()
        self.view.render_servers(servers)
        self._update_all_badges()

    def _setup_network_bindings(self):
        """Rejestruje listenery zdarzeń sieciowych czasu rzeczywistego"""
        self.network.on(PacketType.MESSAGE_RECV, self._on_network_message)
        self.network.on(PacketType.TYPING_START, self._on_network_typing_start)
        self.network.on(PacketType.TYPING_STOP, self._on_network_typing_stop)
        self.network.on(PacketType.STATUS_UPDATE, self._on_network_status_update)
        self.network.on(PacketType.PRESENCE_CHANGE, self._on_network_status_update)
        self.network.on(PacketType.REACTION_UPDATE, self._on_network_reaction)
        self.network.on(PacketType.MESSAGE_DELETE, self._on_network_message_delete)
        self.network.on(PacketType.MEMBER_TIMEOUT, self._on_network_member_timeout)
        self.network.on_state_change(self._on_connection_state_change)

        # Ustaw początkowy stan
        self._on_connection_state_change(self.network.metrics.state)

    def _on_network_status_update(self, packet: Packet):
        """Obsługa aktualizacji statusu innego użytkownika w sieci"""
        user = packet.payload.get("user", "")
        status = packet.payload.get("status", "online")
        custom_status = packet.payload.get("custom_status", "")

        if not user or user.lower() == self.sender_name.lower():
            return

        self.presence_tracker.set_user_presence(user, status, custom_status)
        if hasattr(self.view, "update_user_presence"):
            self.view.update_user_presence(user, status, custom_status)

    def handle_status_menu_click(self):
        """Obsługuje kliknięcie w panel użytkownika - otwiera modal wyboru statusu"""
        if hasattr(self.view, "show_status_selection_modal"):
            self.view.show_status_selection_modal(
                current_status=self.my_status,
                current_custom_status=self.my_custom_status,
                callback=self._on_status_selected
            )

    def _on_status_selected(self, new_status: str, custom_status: str):
        """Callback po wybraniu nowego statusu przez użytkownika"""
        self.my_status = new_status
        self.my_custom_status = custom_status

        # 1. Aktualizacja widoku lokalnego
        if hasattr(self.view, "update_my_status"):
            self.view.update_my_status(new_status, custom_status)

        # 2. Tryb DND (wyciszanie powiadomień)
        is_dnd = (new_status.lower() == "dnd")
        self.notifier.set_dnd_mode(is_dnd)

        # 3. Zapis trwałego statusu w bazie SQLite
        if self.db:
            uid = self.current_user.get("id") or self.current_user.get("email", "")
            self.db.update_user_status(uid, new_status, custom_status)

        # 4. Rozgłoszenie nowego statusu przez sieć WebSocket
        if self.network:
            self.network.send_status(
                user=self.sender_name,
                status=new_status,
                custom_status=custom_status
            )

        print(f"Zaktualizowano status profilu: {new_status} ('{custom_status}')")

    def _load_conversation_history(self, conversation_name: str):
        """Pobiera historię z SQLite i ładuje do wirtualnego widoku"""
        history = self.chat_model.get_history(
            conversation=conversation_name,
            current_user=self.sender_name,
            limit=200
        )
        if history:
            self.view.load_message_history(history)
        else:
            self.view.clear_chat_messages()

    def _on_network_message(self, packet: Packet):
        """Obsługa odebranej wiadomości czatu w czasie rzeczywistym"""
        sender = packet.payload.get("sender", "Anonim")
        target = packet.payload.get("target", "Direct Messages")
        content = packet.payload.get("content", "")
        is_dm = packet.payload.get("is_dm", True)
        attachments = packet.payload.get("attachments", [])

        # Sprawdź czy wiadomość dotyczy aktualnie otwartej konwersacji/kanału
        if is_dm:
            is_active = (self.current_channel is None and (sender == self.current_conversation or target == self.current_conversation))
        else:
            is_active = (self.current_channel is not None and target == self.current_conversation)

        # 1. Trwały zapis w bazie SQLite z odpowiednim statusem przeczytania
        message_id = self.chat_model.save_message(
            sender=sender,
            target=target,
            content=content,
            packet_id=packet.id,
            is_dm=is_dm,
            is_read=is_active
        )
        if message_id and self.db:
            for attachment in attachments:
                self.db.save_attachment(
                    message_id=message_id,
                    filename=attachment.get("filename", ""),
                    original_name=attachment.get("original_name", ""),
                    file_type=attachment.get("file_type", "file"),
                    file_size=attachment.get("file_size", 0),
                    mime_type=attachment.get("mime_type", "application/octet-stream"),
                    file_path=attachment.get("file_path", ""),
                    thumbnail_path=attachment.get("thumbnail_path")
                )

        # 2. Wyświetl w UI jeśli dotyczy otwartej konwersacji, w przeciwnym razie wyślij powiadomienie
        if is_active:
            is_bot = "bot" in sender.lower()
            self.view.add_message(
                sender=sender,
                text=content,
                is_own=False,
                is_bot=is_bot,
                attachments=attachments,
                message_id=message_id
            )
        else:
            # Powiadomienie Windows Toast & In-App
            if is_dm:
                notif_title = f"Voxen • {sender}"
            else:
                ch_display = target.split("#")[-1] if "#" in target else target
                notif_title = f"Voxen • #{ch_display}"

            self.notifier.notify(title=notif_title, message=content)
            self._update_all_badges()

    def _on_network_message_delete(self, packet: Packet) -> None:
        message_id = packet.payload.get("message_id")
        if message_id and self.chat_model.delete_message(int(message_id)):
            self._load_conversation_history(self.current_conversation)

    def _on_network_member_timeout(self, packet: Packet) -> None:
        server_id = packet.payload.get("server_id")
        user_id = packet.payload.get("user_id")
        expires_at = packet.payload.get("expires_at")
        if server_id and user_id and expires_at:
            self.db.timeout_server_member(int(server_id), int(user_id), expires_at)
            if hasattr(self.view, "show_in_app_toast"):
                self.view.show_in_app_toast(
                    "Moderacja",
                    f"Użytkownik został wyciszony do {expires_at}"
                )

    def _on_network_reaction(self, packet: Packet) -> None:
        """Handles a reaction update received from the network."""
        message_id = packet.payload.get("message_id")
        emoji = packet.payload.get("emoji", "")
        user = packet.payload.get("user", "")
        if not message_id or not emoji or not self.db:
            return
        self.db.toggle_message_reaction(int(message_id), user, emoji)
        self._load_conversation_history(self.current_conversation)

    def _on_network_typing_start(self, packet: Packet):
        """Obsługa wskaźnika rozpoczęcia pisania (Multi-User)"""
        user = packet.payload.get("user", "")
        target = packet.payload.get("target", "")

        if not user or user.lower() == self.sender_name.lower():
            return

        # Ustalanie klucza konwersacji (dla DM lub kanału)
        conv_key = target if (target and target != self.sender_name) else user
        if self.current_channel is not None and target == self.current_conversation:
            conv_key = self.current_conversation
        elif self.current_channel is None and (user == self.current_conversation or target == self.current_conversation):
            conv_key = self.current_conversation

        self.typing_tracker.user_started_typing(conv_key, user)
        if conv_key == self.current_conversation:
            self._refresh_typing_indicator()

    def _on_network_typing_stop(self, packet: Packet):
        """Obsługa wskaźnika zakończenia pisania (Multi-User)"""
        user = packet.payload.get("user", "")
        target = packet.payload.get("target", "")

        if not user or user.lower() == self.sender_name.lower():
            return

        conv_key = target if (target and target != self.sender_name) else user
        if self.current_channel is not None and target == self.current_conversation:
            conv_key = self.current_conversation
        elif self.current_channel is None and (user == self.current_conversation or target == self.current_conversation):
            conv_key = self.current_conversation

        self.typing_tracker.user_stopped_typing(conv_key, user)
        if conv_key == self.current_conversation:
            self._refresh_typing_indicator()

    def _on_connection_state_change(self, state: ConnectionState):
        """Aktualizacja wskaźnika stanu sieci w UI"""
        state_map = {
            ConnectionState.DISCONNECTED: ("🔴 Rozłączono", Colors.ERROR),
            ConnectionState.FAILED: ("🔴 Błąd sieci", Colors.ERROR),
            ConnectionState.CONNECTING: ("🟡 Łączenie...", Colors.IDLE),
            ConnectionState.RECONNECTING: ("🟡 Wznawianie...", Colors.IDLE),
            ConnectionState.CONNECTED: ("🟢 Połączono", Colors.ONLINE),
            ConnectionState.AUTHENTICATED: (
                f"🟢 Połączono ({self.network.metrics.latency_ms:.0f} ms)"
                if self.network and self.network.metrics.latency_ms > 0
                else "🟢 Połączono",
                Colors.ONLINE
            ),
        }
        text, color = state_map.get(state, ("⚪ Offline", Colors.OFFLINE))
        self.view.update_network_status(text, color)

    # ==========================================
    # OBSŁUGA SERWERÓW I KANAŁÓW
    # ==========================================

    def handle_server_click(self, server_id, server_name):
        """Obsługuje przełączenie serwera"""
        if server_name == "Direct Messages" or server_id is None:
            print("Przełączono na Direct Messages")
            self.current_server = "Direct Messages"
            self.current_server_id = None
            self.current_channel = None
            self.view.show_dms_sidebar()
            self.handle_conversation_click("Unity Bot")
            return

        print(f"Wybrano serwer: {server_name} (ID: {server_id})")
        self.current_server = server_name
        self.current_server_id = server_id

        # Pobierz kanały dla serwera z SQLite
        uid = self.current_user.get("id", 1)
        role = self.server_model.get_member_role(server_id, uid)
        channels = self.server_model.get_accessible_channels(server_id, role)
        self.view.show_server_channels(server_id, server_name, channels)
        uid = self.current_user.get("id", 1)
        role = self.server_model.get_member_role(server_id, uid)
        can_manage = self.server_model.can_manage(server_id, uid)
        if hasattr(self.view, "set_server_role_permissions"):
            self.view.set_server_role_permissions(role, can_manage)
        self._update_all_badges()

        # Automatycznie wybierz pierwszy kanał (np. #ogólny)
        if channels:
            first_ch = channels[0]
            self.handle_channel_click(
                server_id=server_id,
                channel_name=first_ch["name"],
                topic=first_ch.get("topic", "")
            )
        else:
            self.current_channel = None
            self.current_conversation = server_name
            self.view.update_chat_title(f"📁 {server_name}")
            self.view.clear_chat_messages()

    def handle_channel_click(self, server_id: int, channel_name: str, topic: str = ""):
        """Obsługuje kliknięcie kanału tekstowego na serwerze"""
        self.handle_user_stop_typing()
        self.current_channel = channel_name
        channel_key = f"{self.current_server}#{channel_name}"
        self.current_conversation = channel_key

        print(f"Otwarto kanał #{channel_name} w serwerze {self.current_server}")
        self.view.update_chat_title(f"# {channel_name}", topic=topic)
        self.view.highlight_active_channel(channel_name)
        self._refresh_typing_indicator()
        self.chat_model.mark_as_read(channel_key, self.sender_name)
        self._load_conversation_history(channel_key)
        self._update_all_badges()

    def handle_add_server_click(self):
        """Otwiera okno dialogowe tworzenia nowego serwera"""
        self.view.show_create_server_modal(self._on_server_created)

    def _on_server_created(self, name: str, icon: str):
        """Callback po utworzeniu nowego serwera"""
        success, result = self.server_model.create_server(
            name=name,
            icon=icon,
            owner_id=self.current_user.get("id", 1)
        )
        if success:
            print(f"Utworzono serwer: {name}")
            self.load_servers()
            self.handle_server_click(result["id"], result["name"])
        else:
            print(f"Błąd tworzenia serwera: {result}")

    def handle_analytics_click(self, server_id: int) -> None:
        """Opens aggregate analytics for a server."""
        if server_id is None:
            return
        analytics = self.server_model.get_analytics(server_id)
        if hasattr(self.view, "show_server_analytics_modal"):
            self.view.show_server_analytics_modal(analytics)

    def handle_manage_members_click(self, server_id: int) -> None:
        """Opens server membership management for Owner/Admin users."""
        actor_id = self.current_user.get("id", 1)
        if not self.server_model.can_manage(server_id, actor_id):
            if hasattr(self.view, "show_in_app_toast"):
                self.view.show_in_app_toast("Uprawnienia", "Tylko właściciel lub administrator może zarządzać członkami.")
            return
        members = self.server_model.get_members(server_id)
        available = self.server_model.get_available_users(server_id)

        def refresh() -> None:
            self.handle_manage_members_click(server_id)

        def add_member(user_id: int, role: str) -> None:
            success, result = self.server_model.add_member(server_id, user_id, role)
            if success:
                self.server_model.log_activity(
                    server_id,
                    actor_id,
                    "member_added",
                    user_id,
                    f"Role set to {role}"
                )
            if not success and hasattr(self.view, "show_in_app_toast"):
                self.view.show_in_app_toast("Członkowie", str(result))
            refresh()

        def set_role(user_id: int, role: str) -> None:
            success, result = self.server_model.set_member_role(
                server_id,
                user_id,
                role,
                actor_id
            )
            if not success and hasattr(self.view, "show_in_app_toast"):
                self.view.show_in_app_toast("Członkowie", str(result))
            refresh()

        def remove_member(user_id: int) -> None:
            success, result = self.server_model.remove_member(server_id, user_id)
            if success:
                self.server_model.log_activity(
                    server_id,
                    actor_id,
                    "member_removed",
                    user_id,
                    "Member removed"
                )
            if hasattr(self.view, "show_in_app_toast"):
                self.view.show_in_app_toast("Członkowie", str(result))
            refresh()

        def show_activity() -> None:
            logs = self.server_model.get_activity_logs(server_id, limit=200)
            self.view.show_activity_logs_modal(self.current_server, logs)

        self.view.show_manage_members_modal(
            server_name=self.current_server,
            members=members,
            available_users=available,
            add_callback=add_member,
            role_callback=set_role,
            remove_callback=remove_member,
            activity_callback=show_activity
        )

    def handle_add_channel_click(self, server_id: int):
        """Otwiera okno dialogowe tworzenia kanału tekstowego"""
        uid = self.current_user.get("id", 1)
        if not self.server_model.can_manage(server_id, uid):
            if hasattr(self.view, "show_in_app_toast"):
                self.view.show_in_app_toast("Uprawnienia", "Tylko właściciel lub administrator może tworzyć kanały.")
            return
        self.view.show_create_channel_modal(
            server_name=self.current_server,
            callback=lambda cname, ctopic: self._on_channel_created(server_id, cname, ctopic)
        )

    def _on_channel_created(self, server_id: int, channel_name: str, topic: str):
        """Callback po utworzeniu nowego kanału"""
        uid = self.current_user.get("id", 1)
        success, result = self.server_model.create_channel(
            server_id=server_id,
            name=channel_name,
            topic=topic,
            actor_id=uid
        )
        if success:
            print(f"Utworzono kanał #{channel_name} na serwerze {self.current_server}")
            channels = self.server_model.get_channels(server_id)
            self.view.show_server_channels(server_id, self.current_server, channels)
            self.handle_channel_click(server_id, channel_name, topic)
        else:
            print(f"Błąd tworzenia kanału: {result}")

    def handle_conversation_click(self, name):
        """Obsługuje przełączenie konwersacji DM i załadowanie jej historii z SQLite"""
        print(f"Otwarto konwersację z: {name}")
        self.handle_user_stop_typing()
        self.current_conversation = name
        self.view.update_chat_title(f"💬 {name}")
        self._refresh_typing_indicator()
        self.chat_model.mark_as_read(name, self.sender_name)
        self._load_conversation_history(name)
        self._update_all_badges()

    def _update_all_badges(self):
        """Aktualizuje wszystkie odznaki nieprzeczytanych wiadomości w UI (DMs, kanały, serwery)"""
        unread_map = self.chat_model.get_all_unread_counts(self.sender_name)

        # 1. Odznaki dla konwersacji prywatnych (DMs)
        known_dms = ["Wincekk", "Maxi3049", "Nemeczek", "Unity Bot", "Kapi", "Chaos"]
        total_dm_unread = 0
        for dm_name in known_dms:
            cnt = unread_map.get(dm_name, 0)
            total_dm_unread += cnt
            self.view.update_dm_badge(dm_name, cnt)

        # Badge dla przycisku Direct Messages (Home icon w lewej kolumnie)
        self.view.update_server_badge(None, total_dm_unread)

        # 2. Odznaki dla serwerów i ich kanałów
        servers = self.server_model.get_all_servers()
        for s in servers:
            s_id = s["id"]
            s_name = s["name"]
            channels = self.server_model.get_channels(s_id)
            server_unread = 0

            for ch in channels:
                ch_key = f"{s_name}#{ch['name']}"
                ch_cnt = unread_map.get(ch_key, 0)
                server_unread += ch_cnt

                # Jeśli aktualnie oglądamy ten serwer, zaktualizuj badge kanału
                if self.current_server_id == s_id:
                    self.view.update_channel_badge(ch["name"], ch_cnt)

            self.view.update_server_badge(s_id, server_unread)

    def handle_tab_click(self, tab_name):
        """Obsługuje kliknięcie taba"""
        print(f"Wybrano tab: {tab_name}")
        self.current_tab = tab_name

    def handle_user_typing(self):
        """Obsługuje zdarzenie pisania przez lokalnego użytkownika (throttling i debounce)"""
        if not self.network or not self.current_conversation:
            return

        now = time.time()
        target = self.current_conversation

        # 1. Throttling wysyłania pakietu rozpoczęcia pisania (co max 2.5s)
        if now - self._last_typing_sent > 2.5:
            self.network.send_typing(user=self.sender_name, target=target, is_typing=True)
            self._last_typing_sent = now

        # 2. Reset timera bezczynności (jeśli brak znaków przez 3s -> wyślij TYPING_STOP)
        if hasattr(self.view, "after"):
            if self._typing_stop_timer:
                try:
                    self.view.after_cancel(self._typing_stop_timer)
                except Exception:
                    pass
            try:
                self._typing_stop_timer = self.view.after(3000, self.handle_user_stop_typing)
            except Exception:
                pass

    def handle_user_stop_typing(self):
        """Wysyła zakończenie pisania i czyści timery"""
        if self._typing_stop_timer and hasattr(self.view, "after_cancel"):
            try:
                self.view.after_cancel(self._typing_stop_timer)
            except Exception:
                pass
            self._typing_stop_timer = None

        self._last_typing_sent = 0.0
        if self.network and self.current_conversation:
            self.network.send_typing(
                user=self.sender_name,
                target=self.current_conversation,
                is_typing=False
            )

    def handle_send_message(self, message):
        """Obsługuje wysyłanie wiadomości na czacie lub kanale"""
        if not message.strip():
            return
        if self.current_channel and self.current_server_id:
            uid = self.current_user.get("id", 1)
            role = self.server_model.get_member_role(self.current_server_id, uid)
            channel = next(
                (
                    item for item in self.server_model.get_channels(self.current_server_id)
                    if item["name"] == self.current_channel
                ),
                None
            )
            if channel and not self.server_model.can_access_channel(
                channel["id"],
                role,
                "send"
            ):
                if hasattr(self.view, "show_in_app_toast"):
                    self.view.show_in_app_toast("Uprawnienia", "Nie masz uprawnień do wysyłania na tym kanale.")
                return

        # Zakończ stan pisania po wysłaniu
        self.handle_user_stop_typing()

        target = self.current_conversation or "Direct Messages"
        is_dm = (self.current_channel is None)

        # 1. Wyczyść pole tekstowe w widoku
        self.view.clear_message_input()

        # 2. Trwały zapis w bazie SQLite
        message_id = self.chat_model.save_message(
            sender=self.sender_name,
            target=target,
            content=message,
            is_dm=is_dm
        )

        # 3. Wyświetl natychmiast własną wiadomość w wirtualnym czacie
        reactions = self.db.get_message_reactions(message_id) if message_id and self.db else []
        self.view.add_message(
            sender=self.sender_name,
            text=message,
            is_own=True,
            reactions=reactions,
            message_id=message_id
        )

        # 4. Wyślij asynchronicznie przez Network Engine do sieci
        if self.network:
            self.network.send_message(
                target=target,
                content=message,
                sender=self.sender_name,
                is_dm=is_dm
            )
        else:
            print(f"[Offline] Zapisano do bazy dla {target}: {message}")

    def handle_attach_click(self):
        """Opens a file dialog, validates and stores a selected attachment."""
        file_path = filedialog.askopenfilename(
            title="Wybierz plik",
            filetypes=[("Wszystkie pliki", "*.*")]
        )
        if not file_path:
            return

        try:
            valid, error = self.file_manager.validate_file(file_path)
            if not valid:
                if hasattr(self.view, "show_in_app_toast"):
                    self.view.show_in_app_toast("Załącznik", error)
                return

            metadata = self.file_manager.store_file(file_path)
            target = self.current_conversation or "Direct Messages"
            is_dm = self.current_channel is None

            message_id = self.chat_model.save_message(
                sender=self.sender_name,
                target=target,
                content=f"Załącznik: {metadata['original_name']}",
                is_dm=is_dm
            )
            if message_id and self.db:
                self.db.save_attachment(
                    message_id=message_id,
                    filename=metadata["filename"],
                    original_name=metadata["original_name"],
                    file_type=metadata["file_type"],
                    file_size=metadata["file_size"],
                    mime_type=metadata["mime_type"],
                    file_path=metadata["file_path"],
                    thumbnail_path=metadata["thumbnail_path"]
                )

            self.view.add_message(
                sender=self.sender_name,
                text=f"Załącznik: {metadata['original_name']}",
                is_own=True,
                attachments=[metadata],
                message_id=message_id
            )

            if self.network:
                self.network.send_message(
                    target=target,
                    content=f"Załącznik: {metadata['original_name']}",
                    sender=self.sender_name,
                    is_dm=is_dm,
                    attachments=[metadata]
                )
        except (OSError, ValueError) as exc:
            if hasattr(self.view, "show_in_app_toast"):
                self.view.show_in_app_toast("Załącznik", str(exc))

    def handle_emoji_click(self):
        """Opens the emoji picker and inserts the selected emoji."""
        if hasattr(self.view, "show_emoji_picker"):
            self.view.show_emoji_picker(self._insert_emoji)

    def _insert_emoji(self, emoji: str) -> None:
        if hasattr(self.view, "message_entry"):
            current = self.view.message_entry.get()
            self.view.message_entry.delete(0, "end")
            self.view.message_entry.insert(0, f"{current}{emoji}")

    def handle_delete_message(self, message_id: str) -> None:
        """Deletes a message when the active member can moderate."""
        try:
            db_message_id = int(message_id)
        except (TypeError, ValueError):
            return
        if self.current_channel is None:
            can_moderate = False
        elif self.current_server_id:
            actor_id = self.current_user.get("id", 1)
            can_moderate = self.server_model.can_moderate(
                self.current_server_id,
                actor_id
            )
        else:
            can_moderate = False
        if not can_moderate:
            return
        if self.chat_model.delete_message(db_message_id):
            if self.current_server_id:
                self.server_model.log_activity(
                    self.current_server_id,
                    self.current_user.get("id", 1),
                    "message_deleted",
                    None,
                    f"Message {db_message_id} deleted"
                )
            self._load_conversation_history(self.current_conversation)
            if self.network:
                self.network.send_message_delete(
                    db_message_id,
                    self.current_conversation or "Direct Messages"
                )

    def handle_toggle_pin(self, message_id: str) -> None:
        """Pins or unpins a message in the active conversation."""
        try:
            db_message_id = int(message_id)
        except (TypeError, ValueError):
            return

        if self.current_server_id:
            actor_id = self.current_user.get("id", 1)
            if not self.server_model.can_moderate(self.current_server_id, actor_id):
                return
        if self.chat_model.is_message_pinned(db_message_id):
            success = self.chat_model.unpin_message(db_message_id)
            action = "unpinned"
        else:
            success, _ = self.chat_model.pin_message(
                db_message_id,
                self.current_conversation or "Direct Messages",
                self.sender_name
            )
            action = "pinned"

        if success:
            if self.current_server_id:
                self.server_model.log_activity(
                    self.current_server_id,
                    self.current_user.get("id", 1),
                    f"message_{action}",
                    None,
                    f"Message {db_message_id} {action}"
                )
            self._load_conversation_history(self.current_conversation)

    def handle_show_pinned_messages(self) -> None:
        """Shows pinned messages for the active conversation."""
        pinned = self.chat_model.get_pinned_messages(
            self.current_conversation or "Direct Messages"
        )
        if hasattr(self.view, "show_pinned_messages_modal"):
            self.view.show_pinned_messages_modal(pinned)

    def handle_timeout_member(self, user_name: str, minutes: int = 10) -> None:
        """Times out a member in the active server."""
        if not self.current_server_id:
            return
        actor_id = self.current_user.get("id", 1)
        if not self.server_model.can_moderate(self.current_server_id, actor_id):
            return
        member = next(
            (
                item for item in self.server_model.get_members(self.current_server_id)
                if item["username"].lower() == user_name.strip().lower()
                or item["email"].lower() == user_name.strip().lower()
            ),
            None
        )
        if not member:
            return
        success, expires_at = self.server_model.timeout_member(
            self.current_server_id,
            member["user_id"],
            minutes
        )
        if success:
            self.server_model.log_activity(
                self.current_server_id,
                actor_id,
                "member_timeout",
                member["user_id"],
                f"Timeout expires at {expires_at}"
            )
        if success and self.network:
            self.network.send_member_timeout(
                server_id=self.current_server_id,
                user_id=member["user_id"],
                user_name=user_name,
                expires_at=expires_at
            )

    def handle_message_reaction(self, message_id: str, emoji: str) -> None:
        """Toggles a user's reaction and broadcasts it."""
        try:
            db_message_id = int(message_id)
        except (TypeError, ValueError):
            return
        if not self.db:
            return
        self.db.toggle_message_reaction(db_message_id, self.sender_name, emoji)
        self._load_conversation_history(self.current_conversation)
        if self.network:
            self.network.send_reaction(
                message_id=db_message_id,
                emoji=emoji,
                user=self.sender_name,
                target=self.current_conversation or "Direct Messages",
                is_dm=self.current_channel is None
            )

    def handle_settings_click(self):
        """Obsługuje wylogowanie i powrót do ekranu logowania"""
        print("Wylogowywanie użytkownika i unieważnianie sesji...")
        from models.auth_model import AuthModel
        AuthModel().logout()
        self.app.show_login_screen()

    def handle_search(self, query):
        """Obsługuje wyszukiwanie konwersacji po nazwie."""
        query = query.strip().lower()
        if not hasattr(self.view, "conversations_scroll"):
            return
        for widget in self.view.conversations_scroll.winfo_children():
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except Exception:
                    continue
                if isinstance(text, str) and (not query or query in text.lower()):
                    widget.pack()
                    break
            else:
                if query:
                    widget.pack_forget()

    def handle_channel_search(self, query: str = "", sort_by: str = "position") -> None:
        """Filters and sorts channels for the active server."""
        if not self.current_server_id:
            return
        channels = self.server_model.search_channels(
            self.current_server_id,
            query=query,
            sort_by=sort_by
        )
        uid = self.current_user.get("id", 1)
        role = self.server_model.get_member_role(self.current_server_id, uid)
        channels = [
            channel for channel in channels
            if self.server_model.can_access_channel(
                channel["id"],
                role,
                "view"
            )
        ]
        self.view.show_server_channels(
            self.current_server_id,
            self.current_server,
            channels
        )

    def handle_history_search(self, query: str = "", sender: str = "", timestamp: str = ""):
        """Filters the active conversation/channel history."""
        query = query.strip()
        sender = sender.strip()
        timestamp = timestamp.strip()
        if not query and not sender and not timestamp:
            self._load_conversation_history(self.current_conversation)
            return
        history = self.chat_model.search_history(
            conversation=self.current_conversation,
            current_user=self.sender_name,
            query=query,
            sender=sender,
            timestamp=timestamp,
            limit=200
        )
        if history:
            self.view.load_message_history(history)
        else:
            self.view.clear_chat_messages()

    def search_history(self, query: str = "", sender: str = "", timestamp: str = ""):
        """Alias for handle_history_search."""
        self.handle_history_search(query=query, sender=sender, timestamp=timestamp)
