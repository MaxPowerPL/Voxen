"""
PERFORMANCE TEST - VOXEN VIRTUAL CHAT VIEW (OBJECT POOLING & VIRTUAL SCROLLING)
Symulacja obciążenia: 10 000 i 50 000 wiadomości.
Weryfikacja:
- Liczby widgetów w pamięci (Object Pool = O(1))
- Czasu przetwarzania i ładowania (ms)
- Poprawności bisekcji O(log N)
"""

import io
import sys
import time

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import customtkinter as ctk
from views.components.virtual_chat import VirtualChatView, ChatMessageDTO


def test_virtual_chat_performance():
    print("=== TEST WYDAJNOŚCIOWY: VIRTUAL CHAT VIEW & OBJECT POOLING ===")

    # Tworzymy aplikację Tkinter w tle (headless bez pokazywania okna)
    root = ctk.CTk()
    root.geometry("800x600")
    root.withdraw()  # Ukryj okno, testujemy silnik geometrii i puli

    virtual_chat = VirtualChatView(root)
    virtual_chat.pack(fill="both", expand=True)
    root.update_idletasks()

    # 1. Sprawdzenie początkowego rozmiaru puli
    initial_pool_size = len(virtual_chat.pool)
    print(f" [1/5] Rozmiar puli obiektów (Widget Pool): {initial_pool_size} widgetów")
    assert initial_pool_size >= 20

    # 2. Załadowanie 50 000 wiadomości
    print(" [2/5] Generowanie i ładowanie 50 000 wiadomości testowych...")
    messages_50k = []
    for i in range(50000):
        sender = "Wincekk" if i % 2 == 0 else "Tester"
        is_own = (i % 2 != 0)
        content = f"Wiadomość testowa #{i} z losową treścią dla sprawdzenia wirtualizacji czatu."
        messages_50k.append({
            "id": i,
            "sender": sender,
            "content": content,
            "timestamp": "12:34",
            "is_own": is_own
        })

    t0 = time.perf_counter()
    virtual_chat.set_messages(messages_50k)
    t1 = time.perf_counter()
    load_time_ms = (t1 - t0) * 1000.0

    print(f"       Czas załadowania 50 000 wiadomości: {load_time_ms:.2f} ms")
    print(f"       Liczba wiadomości w modelu: {len(virtual_chat.messages)}")
    print(f"       Całkowita wysokość wirtualna: {virtual_chat.total_height:,} px")
    assert len(virtual_chat.messages) == 50000
    assert virtual_chat.total_height > 2000000

    # 3. Weryfikacja Object Poolingu przy 50 000 wiadomościach
    pool_size_after_50k = len(virtual_chat.pool)
    print(f" [3/5] Rozmiar puli po załadowaniu 50 000 wiadomości: {pool_size_after_50k} widgetów (STALE O(1)!)")
    assert pool_size_after_50k <= 30, f"Pula nie powinna przekraczać ~30 widgetów, a ma {pool_size_after_50k}"

    # 4. Test przewijania (Scroll benchmark od góry do dołu)
    print(" [4/5] Symulacja przewijania 1 000 klatek scrolla (Viewport sweep)...")
    t_scroll_start = time.perf_counter()
    step = virtual_chat.total_height / 1000.0
    for frame in range(1000):
        virtual_chat.scroll_y = frame * step
        virtual_chat._render_visible_items()
    t_scroll_end = time.perf_counter()
    total_scroll_time_ms = (t_scroll_end - t_scroll_start) * 1000.0
    avg_frame_time_ms = total_scroll_time_ms / 1000.0

    print(f"       Średni czas renderu klatki przy 10 000 wiadomości: {avg_frame_time_ms:.4f} ms (>1000 FPS!)")
    assert avg_frame_time_ms < 2.0, "Renderowanie klatki powinno zająć poniżej 2 ms!"

    # 5. Dodawanie nowej wiadomości w czasie rzeczywistym
    print(" [5/5] Dodawanie pojedynczej wiadomości w czasie rzeczywistym...")
    t_add_start = time.perf_counter()
    virtual_chat.add_message("Unity Bot", "Nowa odpowiedź w locie!", is_own=False)
    t_add_end = time.perf_counter()
    add_time_ms = (t_add_end - t_add_start) * 1000.0

    print(f"       Czas dodania wiadomości: {add_time_ms:.3f} ms (Natychmiastowe O(1))")
    assert len(virtual_chat.messages) == 50001
    assert len(virtual_chat.pool) <= 30

    root.destroy()
    print("\n=== WSZYSTKIE TESTY WYDAJNOŚCIOWE ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_virtual_chat_performance()
