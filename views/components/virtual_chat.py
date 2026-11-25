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
import time
from typing import Callable, List, Optional
import customtkinter as ctk

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

    def bind_data(self, message: ChatMessageDTO, max_width: int = 600) -> None:
        """Szybkie przypisanie nowych danych bez alokacji widgetu"""
        self.avatar_label.configure(
            text=message.avatar,
            fg_color=Colors.BUTTON_SECONDARY if message.is_own else Colors.BG_MAIN
        )

        sender_color = Colors.BUTTON_PRIMARY if message.is_own else (
            Colors.ICON_COLOR if message.is_bot or "Bot" in message.sender else Colors.TEXT_PRIMARY
        )
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

    def add_message(
        self,
        sender: str,
        content: str,
        is_own: bool = False,
        timestamp: Optional[str] = None,
        is_bot: bool = False
    ) -> None:
        """
        Dodaje nową wiadomość do wirtualnej historii czatu.
        Złożoność: O(1). Zero alokacji nowych widgetów!
        """
        if self.welcome_label and self.welcome_label.winfo_ismapped():
            self.welcome_label.place_forget()

        h = self._estimate_message_height(content, self.viewport_width)
        dto = ChatMessageDTO(
            id=str(len(self.messages)),
            sender=sender,
            content=content,
            timestamp=timestamp or datetime.datetime.now().strftime("%H:%M"),
            is_own=is_own,
            is_bot=is_bot,
            calculated_height=h
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
            h = self._estimate_message_height(content, self.viewport_width)
            dto = ChatMessageDTO(
                id=str(item.get("id", len(self.messages))),
                sender=item.get("sender", "User"),
                content=content,
                timestamp=item.get("timestamp", ""),
                is_own=item.get("is_own", False),
                is_bot=item.get("is_bot", False),
                calculated_height=h
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
                h = self._estimate_message_height(msg.content, self.viewport_width)
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

            if widget.cget("height") != item_h:
                widget.configure(height=item_h)
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
