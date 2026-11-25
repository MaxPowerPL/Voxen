"""
VOXEN VIRTUAL CHAT VIEW - OBJECT POOLING & VIRTUAL SCROLLING
Wysokowydajny silnik renderowania historii wiadomości czatu w czasie stałym O(1).
Cechy architektoniczne:
- Wirtualizacja danych: Pamięć dla 100 000 wiadomości wynosi tylko kilka megabajtów (DTO).
- Pula obiektów (Object Pooling): Tylko 20-25 aktywnych widgetów Tkintera w pamięci bez względu na liczbę wiadomości.
- Błyskawiczny binary search (O(log N)) wyznaczający zakres widoczności.
- Pozycjonowanie place() bez globalnego przeliczania geometrii (brak lagów, stałe 60 FPS).
- Obsługa kółka myszy (<MouseWheel>), płynnego paska przewijania oraz auto-scroll (pin-to-bottom).
"""

import bisect
from dataclasses import dataclass, field
import datetime
from math import ceil
import os
import sys
import webbrowser
from pathlib import Path
import time
from typing import Callable, List, Optional
import customtkinter as ctk
from PIL import Image

from utils import Colors, Fonts


@dataclass
class ChatMessageDTO:
    """Lekka struktura danych pojedynczej wiadomości (Zero Widget Overhead)"""
    id: str
    sender: str
    content: str
    timestamp: str = ""
    is_own: bool = False
    is_bot: bool = False
    avatar: str = "👤"
    calculated_height: int = 58
    attachments: list = field(default_factory=list)
    reactions: list = field(default_factory=list)
    is_pinned: bool = False
    reply_context: dict | None = None
    nickname_color: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().strftime("%H:%M")
        if "Bot" in self.sender or self.is_bot:
            self.avatar = "🤖"
        elif self.is_own:
            self.avatar = "⭐"


class PooledMessageWidget(ctk.CTkFrame):
    """
    Pojedynczy widget wiadomości w puli obiektów.
    Nigdy nie jest niszczony – jest recyklingowany i rekonfigurowany nowymi danymi.
    """

    def __init__(self, master):
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=6
        )
        # 1. Awatar
        self.avatar_label = ctk.CTkLabel(
            self,
            text="👤",
            font=("Segoe UI", 18),
            width=36,
            height=36,
            corner_radius=18,
            fg_color=Colors.BG_MAIN
        )
        self.avatar_label.pack(side="left", anchor="n", padx=(4, 10), pady=2)

        # 2. Kontener treści
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(side="left", fill="both", expand=True)

        # 3. Header: Nadawca + Czas
        self.header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.header_frame.pack(anchor="w", fill="x")

        self.sender_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=Fonts.LABEL,
            text_color=Colors.TEXT_PRIMARY
        )
        self.sender_label.pack(side="left", padx=(0, 8))

        self.time_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=("Segoe UI", 10),
            text_color=Colors.TEXT_SECONDARY
        )
        self.time_label.pack(side="left")

        # 4. Treść wiadomości
        self.body_label = ctk.CTkLabel(
            self.content_frame,
            text="",
            font=Fonts.INPUT,
            text_color=Colors.TEXT_INPUT,
            justify="left",
            wraplength=600,
            anchor="w"
        )
        self.body_label.pack(anchor="w", pady=(2, 2))

        self.attachment_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent"
        )
        self.attachment_frame.pack(anchor="w", fill="x", pady=(4, 2))
        self._attachment_images = []
        self.reaction_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent"
        )
        self.reaction_frame.pack(anchor="w", fill="x", pady=(2, 2))
        self._reaction_callback = None
        self._message_id = None
        self._bound_message_id: Optional[str] = None
        self._bound_width: int = 0
        self._bound_height: int = 0
        self._moderation_callback = None
        self._pin_callback = None
        self._reply_callback = None
        self._is_pinned = False
        self.moderation_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent"
        )
        self.moderation_frame.pack(anchor="e", fill="x", pady=(0, 2))
        self._pin_button = ctk.CTkButton(
            self.moderation_frame,
            text="📌",
            width=34,
            height=24,
            fg_color="transparent",
            hover_color=Colors.BUTTON_PRIMARY,
            command=self._on_pin
        )
        self._pin_button.pack_forget()
        self._moderation_button = ctk.CTkButton(
            self.moderation_frame,
            text="🗑",
            width=34,
            height=24,
            fg_color="transparent",
            hover_color=Colors.DND,
            command=self._on_moderate
        )

        self._reply_button = ctk.CTkButton(
            self.moderation_frame,
            text="↩",
            width=34,
            height=24,
            fg_color="transparent",
            hover_color=Colors.BUTTON_PRIMARY,
            command=self._on_reply
        )
        self._reply_button.pack(side="right", padx=(4, 0), pady=2)

    def set_moderation_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        self._moderation_callback = callback

    def set_pin_callback(
        self,
        callback: Optional[Callable[[str], None]],
        enabled: bool = True
    ) -> None:
        self._pin_callback = callback
        if enabled:
            self._pin_button.configure(state="normal")
            self._pin_button.pack(side="right", padx=(4, 0), pady=2)
        else:
            self._pin_button.configure(state="disabled")
            self._pin_button.pack_forget()

    def set_pinned(self, pinned: bool) -> None:
        self._is_pinned = pinned
        self._pin_button.configure(
            text="📌",
            fg_color=Colors.BUTTON_PRIMARY if pinned else "transparent"
        )

    def _on_pin(self) -> None:
        if self._pin_callback:
            self._pin_callback(str(self._message_id))

    def set_reply_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        self._reply_callback = callback

    def _on_reply(self) -> None:
        if self._reply_callback:
            self._reply_callback(str(self._message_id))

    def set_moderation_enabled(self, enabled: bool) -> None:
        self._moderation_enabled = enabled
        if enabled:
            self._moderation_button.pack(side="right", padx=(4, 0), pady=2)
        elif self._moderation_button.winfo_ismapped():
            self._moderation_button.pack_forget()

    def _on_moderate(self) -> None:
        if self._moderation_callback:
            self._moderation_callback(str(self._message_id))

    def set_reaction_callback(self, callback: Callable[[str, str], None]) -> None:
        self._reaction_callback = callback

    def _render_reactions(self, message_id: str, reactions: list) -> None:
        for widget in self.reaction_frame.winfo_children():
            widget.destroy()
        self._message_id = message_id
        for reaction in reactions or []:
            emoji = reaction.get("emoji", "")
            count = reaction.get("count", 0)
            button = ctk.CTkButton(
                self.reaction_frame,
                text=f"{emoji} {count}",
                width=52,
                height=24,
                fg_color=Colors.BG_RIGHT,
                hover_color=Colors.BUTTON_PRIMARY,
                command=lambda e=emoji: self._on_reaction(e)
            )
            button.pack(side="left", padx=(0, 4), pady=2)

    def _on_reaction(self, emoji: str) -> None:
        if self._reaction_callback:
            self._reaction_callback(str(self._message_id), emoji)

    def _open_attachment(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            else:
                webbrowser.open(path.as_uri())
        except OSError:
            webbrowser.open(path.as_uri())

    def _render_attachments(self, attachments: list) -> None:
        if not attachments and not self.attachment_frame.winfo_children():
            return
        for widget in self.attachment_frame.winfo_children():
            widget.destroy()
        self._attachment_images = []

        for attachment in attachments or []:
            original_name = attachment.get("original_name") or attachment.get("filename") or "Plik"
            thumbnail_path = attachment.get("thumbnail_path")
            file_path = attachment.get("file_path") or attachment.get("path") or ""
            file_type = attachment.get("file_type", "")

            if file_type == "image" and thumbnail_path and Path(thumbnail_path).exists():
                try:
                    pil_image = Image.open(thumbnail_path)
                    pil_image.thumbnail((320, 320), Image.Resampling.LANCZOS)
                    ctk_image = ctk.CTkImage(
                        light_image=pil_image,
                        dark_image=pil_image,
                        size=(pil_image.width, pil_image.height)
                    )
                    self._attachment_images.append(ctk_image)
                    image_button = ctk.CTkButton(
                        self.attachment_frame,
                        image=ctk_image,
                        text="",
                        fg_color="transparent",
                        hover_color=Colors.BG_MAIN,
                        command=lambda path=file_path: self._open_attachment(path)
                    )
                    image_button.pack(anchor="w", pady=(0, 4))
                    continue
                except (OSError, ValueError):
                    pass

            file_size = attachment.get("file_size") or attachment.get("size") or 0
            if file_size < 1024 * 1024:
                size_text = f"{file_size / 1024:.1f} KB"
            else:
                size_text = f"{file_size / (1024 * 1024):.1f} MB"
            card = ctk.CTkButton(
                self.attachment_frame,
                text=f"📎 {original_name}\n{size_text}",
                fg_color=Colors.BG_RIGHT,
                hover_color=Colors.BG_MAIN,
                text_color=Colors.TEXT_PRIMARY,
                anchor="w",
                command=lambda path=file_path: self._open_attachment(path)
            )
            card.pack(anchor="w", fill="x", pady=(0, 4))

    def bind_data(self, message: ChatMessageDTO, max_width: int = 600) -> None:
        """Szybkie przypisanie nowych danych bez alokacji widgetu"""
        if self._bound_message_id == message.id and self._bound_width == max_width:
            return
        self._bound_message_id = message.id
        self._bound_width = max_width
        self.avatar_label.configure(
            text=message.avatar,
            fg_color=Colors.BUTTON_SECONDARY if message.is_own else Colors.BG_MAIN
        )

        sender_color = message.nickname_color or (Colors.BUTTON_PRIMARY if message.is_own else (
            Colors.ICON_COLOR if message.is_bot or "Bot" in message.sender else Colors.TEXT_PRIMARY
        ))
        self.sender_label.configure(
            text=message.sender,
            text_color=sender_color
        )
        self.time_label.configure(text=message.timestamp)

        # Dopasowanie zawijania tekstu do szerokości okna
        wrap_val = max(250, max_width - 80)
        self.body_label.configure(
            text=message.content,
            wraplength=wrap_val
        )
        self._render_attachments(message.attachments)
        self._render_reactions(message.id, message.reactions)
        self.set_moderation_enabled(getattr(self, "_moderation_enabled", False))
        self.set_pinned(getattr(message, "is_pinned", False))


class VirtualChatView(ctk.CTkFrame):
    """
    Wirtualizowany kontener czatu.
    Utrzymuje stałą liczbę widgetów (Object Pool) i renderuje tylko widoczny wycinek.
    """

    INITIAL_POOL_SIZE = 22
    LINE_HEIGHT = 20
    BASE_PADDING = 38
    APPROX_CHARS_PER_LINE = 65

    def __init__(self, master, fg_color="transparent"):
        super().__init__(master, fg_color=fg_color)

        # Tablica wiadomości (Lekkie DTO)
        self.messages: List[ChatMessageDTO] = []
        # Tablica sum prefiksowych wysokości dla bisekcji O(log N)
        self.offsets: List[int] = [0]
        self.total_height: int = 0
        self.reaction_callback: Optional[Callable[[str, str], None]] = None
        self.moderation_callback: Optional[Callable[[str], None]] = None
        self.reply_callback: Optional[Callable[[str], None]] = None
        self.moderation_enabled: bool = False
        self.pin_callback: Optional[Callable[[str], None]] = None
        self.pin_enabled: bool = True

        # Stan widoku i przewijania
        self.viewport_height: int = 1
        self.viewport_width: int = 600
        self.scroll_y: float = 0.0          # Aktualna pozycja scroll w pikselach
        self.is_pinned_to_bottom: bool = True  # Czy auto-scrollować przy nowej wiadomości

        # 1. Prawa kolumna: Dedykowany Custom Scrollbar
        self.scrollbar = ctk.CTkScrollbar(
            self,
            orientation="vertical",
            command=self._on_scrollbar_drag,
            fg_color=Colors.BG_RIGHT,
            button_color=Colors.INPUT_BORDER,
            button_hover_color=Colors.BG_MAIN,
            width=14
        )
        self.scrollbar.pack(side="right", fill="y", padx=(2, 0))

        # 2. Główny kontener widoku wiadomości (Viewport Canvas)
        self.canvas_container = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )
        self.canvas_container.pack(side="left", fill="both", expand=True)

        # Pula obiektów (Widget Pool)
        self.pool: List[PooledMessageWidget] = []
        for _ in range(self.INITIAL_POOL_SIZE):
            widget = PooledMessageWidget(self.canvas_container)
            self.pool.append(widget)

        # Wiadomość powitalna gdy brak wiadomości
        self.welcome_label = ctk.CTkLabel(
            self.canvas_container,
            text="Witaj w Voxen! 👋\n\nNapisz pierwszą wiadomość lub wybierz konwersację.",
            font=Fonts.SUBTITLE,
            text_color=Colors.TEXT_SECONDARY,
            justify="center"
        )
        self.welcome_label.place(relx=0.5, rely=0.5, anchor="center")

        # Obsługa zdarzeń zmiany rozmiaru okna i kółka myszy
        self.canvas_container.bind("<Configure>", self._on_resize)
        self.bind_mousewheel(self)
        self.bind_mousewheel(self.canvas_container)

    def bind_mousewheel(self, target_widget):
        """Rekurencyjne bindowanie kółka myszy dla intuicyjnego przewijania"""
        target_widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        # Linux bindings
        target_widget.bind("<Button-4>", lambda e: self._scroll_by_delta(-40), add="+")
        target_widget.bind("<Button-5>", lambda e: self._scroll_by_delta(40), add="+")

    def _estimate_message_height(self, content: str, width: int) -> int:
        """
        Szybka aproksymacja wysokości wiadomości na podstawie znaków i podziałów linii.
        O(1) bez obciążania silnika renderowania.
        """
        chars_per_line = max(20, (width - 100) // 8)
        lines = 0
        for paragraph in content.split("\n"):
            p_len = len(paragraph)
            lines += max(1, ceil(p_len / chars_per_line))

        return self.BASE_PADDING + (lines * self.LINE_HEIGHT)

    def _estimate_rendered_height(
        self,
        content: str,
        width: int,
        attachments: list | None = None,
        reactions: list | None = None
    ) -> int:
        height = self._estimate_message_height(content, width)
        for attachment in attachments or []:
            if attachment.get("file_type") == "image" and attachment.get("thumbnail_path"):
                height += 220
            else:
                height += 64
        if reactions:
            height += 32
        return height

    def set_reaction_callback(self, callback: Callable[[str, str], None]) -> None:
        self.reaction_callback = callback
        for widget in self.pool:
            widget.set_reaction_callback(callback)

    def set_moderation_callback(
        self,
        callback: Optional[Callable[[str], None]],
        enabled: bool = False
    ) -> None:
        self.moderation_callback = callback
        self.moderation_enabled = enabled
        for widget in self.pool:
            widget.set_moderation_callback(callback)
            widget.set_moderation_enabled(enabled)

    def set_pin_callback(
        self,
        callback: Optional[Callable[[str], None]],
        enabled: bool = True
    ) -> None:
        self.pin_callback = callback
        self.pin_enabled = enabled
        for widget in self.pool:
            widget.set_pin_callback(callback, enabled)

    def set_reply_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        self.reply_callback = callback
        for widget in self.pool:
            widget.set_reply_callback(callback)

    def add_message(
        self,
        sender: str,
        content: str,
        is_own: bool = False,
        timestamp: Optional[str] = None,
        is_bot: bool = False,
        attachments: Optional[list] = None,
        reactions: Optional[list] = None,
        message_id: Optional[int] = None,
        nickname_color: str = ""
    ) -> None:
        """
        Dodaje nową wiadomość do wirtualnej historii czatu.
        Złożoność: O(1). Zero alokacji nowych widgetów!
        """
        if self.welcome_label and self.welcome_label.winfo_ismapped():
            self.welcome_label.place_forget()

        h = self._estimate_rendered_height(content, self.viewport_width, attachments, reactions)
        dto = ChatMessageDTO(
            id=str(message_id if message_id is not None else len(self.messages)),
            sender=sender,
            content=content,
            timestamp=timestamp or datetime.datetime.now().strftime("%H:%M"),
            is_own=is_own,
            is_bot=is_bot,
            calculated_height=h,
            attachments=attachments or [],
            reactions=reactions or [],
            nickname_color=nickname_color
        )

        self.messages.append(dto)
        current_offset = self.offsets[-1]
        self.offsets.append(current_offset + h)
        self.total_height = self.offsets[-1]

        # Jeśli użytkownik był na samym dole, przewijamy automatycznie do nowej wiadomości
        if self.is_pinned_to_bottom:
            self.scroll_to_bottom()
        else:
            self._render_visible_items()
            self._update_scrollbar()

    def set_messages(self, messages_data: List[dict]) -> None:
        """
        Wsadowe załadowanie tysięcy wiadomości (np. historia z SQLite).
        Działa natychmiastowo dzięki wirtualizacji!
        """
        if self.welcome_label and self.welcome_label.winfo_ismapped():
            self.welcome_label.place_forget()

        self.messages.clear()
        self.offsets = [0]

        for item in messages_data:
            content = item.get("content", "")
            attachments = item.get("attachments", [])
            reactions = item.get("reactions", [])
            h = self._estimate_rendered_height(content, self.viewport_width, attachments, reactions)
            dto = ChatMessageDTO(
                id=str(item.get("id", len(self.messages))),
                sender=item.get("sender", "User"),
                content=content,
                timestamp=item.get("timestamp", ""),
                is_own=item.get("is_own", False),
                is_bot=item.get("is_bot", False),
                calculated_height=h,
                attachments=attachments,
                reactions=reactions,
                is_pinned=item.get("is_pinned", False),
                nickname_color=item.get("nickname_color", "")
            )
            self.messages.append(dto)
            self.offsets.append(self.offsets[-1] + h)

        self.total_height = self.offsets[-1] if self.offsets else 0
        self.scroll_to_bottom()

    def clear(self) -> None:
        """Czyści historię wiadomości i chowa widgety z puli"""
        self.messages.clear()
        self.offsets = [0]
        self.total_height = 0
        self.scroll_y = 0.0
        for w in self.pool:
            w.place_forget()
        self.welcome_label.place(relx=0.5, rely=0.5, anchor="center")
        self._update_scrollbar()

    def scroll_to_bottom(self) -> None:
        """Przewija widok na sam dół historii"""
        max_scroll = max(0, self.total_height - self.viewport_height)
        self.scroll_y = float(max_scroll)
        self.is_pinned_to_bottom = True
        self._render_visible_items()
        self._update_scrollbar()

    def _scroll_by_delta(self, delta_px: int) -> None:
        """Płynne przesunięcie pozycji widoku o delta pikseli"""
        max_scroll = max(0, self.total_height - self.viewport_height)
        new_scroll = max(0.0, min(float(max_scroll), self.scroll_y + delta_px))

        # Czy użytkownik przewinął na sam dół (z tolerancją 10px)?
        self.is_pinned_to_bottom = (new_scroll >= max_scroll - 10)
        self.scroll_y = new_scroll

        self._render_visible_items()
        self._update_scrollbar()

    def _on_mousewheel(self, event) -> str:
        """Obsługa kółka myszy w systemie Windows (event.delta standardowo +-120)"""
        delta = -1 * int(event.delta / 120) * 45
        self._scroll_by_delta(delta)
        return "break"

    def _on_scrollbar_drag(self, scroll_ratio: float) -> None:
        """Obsługa przeciągania suwaka paska przewijania"""
        max_scroll = max(0, self.total_height - self.viewport_height)
        self.scroll_y = float(scroll_ratio) * max_scroll
        self.is_pinned_to_bottom = (self.scroll_y >= max_scroll - 10)
        self._render_visible_items()

    def _update_scrollbar(self) -> None:
        """Aktualizacja rozmiaru i pozycji kciuka paska przewijania"""
        if self.total_height <= self.viewport_height or self.total_height == 0:
            self.scrollbar.set(0.0, 1.0)
            return

        start_ratio = self.scroll_y / self.total_height
        end_ratio = min(1.0, (self.scroll_y + self.viewport_height) / self.total_height)
        self.scrollbar.set(start_ratio, end_ratio)

    def _on_resize(self, event) -> None:
        """Reakcja na zmianę geometrii kontenera czatu"""
        if event.width <= 10 or event.height <= 10:
            return

        width_changed = abs(event.width - self.viewport_width) > 30
        self.viewport_width = event.width
        self.viewport_height = event.height

        # Jeśli szerokość uległa znacznej zmianie, przeliczamy wysokości zawijania tekstu
        if width_changed and self.messages:
            self.offsets = [0]
            for msg in self.messages:
                h = self._estimate_rendered_height(msg.content, self.viewport_width, msg.attachments, msg.reactions)
                msg.calculated_height = h
                self.offsets.append(self.offsets[-1] + h)
            self.total_height = self.offsets[-1]

        if self.is_pinned_to_bottom:
            self.scroll_to_bottom()
        else:
            self._render_visible_items()
            self._update_scrollbar()

    def _render_visible_items(self) -> None:
        """
        SERCE ALGORYTMU: Renderuje wyłącznie widoczne elementy przy użyciu Puli Obiektów.
        Złożoność: O(pool_size) = O(1) stały czas CPU!
        """
        if not self.messages:
            for w in self.pool:
                w.place_forget()
            return

        top_y = self.scroll_y
        bottom_y = top_y + self.viewport_height

        # Bisekcja O(log N) do odnalezienia indeksów widocznych wiadomości
        start_idx = bisect.bisect_right(self.offsets, top_y) - 1
        start_idx = max(0, start_idx)

        end_idx = bisect.bisect_left(self.offsets, bottom_y)
        end_idx = min(len(self.messages), end_idx + 1)

        visible_count = end_idx - start_idx

        # Dynamiczne powiększenie puli jeśli ekran pokazuje więcej elementów niż rozmiar puli
        while len(self.pool) < visible_count + 4:
            new_widget = PooledMessageWidget(self.canvas_container)
            new_widget.set_reaction_callback(self.reaction_callback)
            new_widget.set_moderation_callback(self.moderation_callback)
            new_widget.set_moderation_enabled(self.moderation_enabled)
            self.bind_mousewheel(new_widget)
            self.bind_mousewheel(new_widget.content_frame)
            self.bind_mousewheel(new_widget.body_label)
            self.pool.append(new_widget)

        # Przypisanie danych i pozycjonowanie widocznych widgetów
        pool_idx = 0
        for i in range(start_idx, end_idx):
            msg_dto = self.messages[i]
            widget = self.pool[pool_idx]

            # Obliczenie współrzędnej Y wewnątrz viewportu
            item_y = self.offsets[i] - top_y
            item_h = msg_dto.calculated_height

            if getattr(widget, "_bound_height", 0) != item_h:
                widget.configure(height=item_h)
                widget._bound_height = item_h
            widget.bind_data(msg_dto, max_width=self.viewport_width)
            widget.place(
                x=6,
                y=int(item_y),
                relwidth=0.98
            )
            pool_idx += 1

        # Ukrycie niewykorzystanych widgetów z puli (place_forget)
        for i in range(pool_idx, len(self.pool)):
            if self.pool[i].winfo_ismapped():
                self.pool[i].place_forget()
