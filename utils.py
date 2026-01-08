"""
Plik konfiguracyjny z kolorami i ustawieniami dla aplikacji Discord
"""

# === KOLORY DLA CIEMNEGO MOTYWU ===
# Kolory są zdefiniowane jako tuple: (kolor_jasny, kolor_ciemny)
# lub pojedyncze wartości dla obu motywów

class Colors:
    """Klasa zawierająca wszystkie kolory aplikacji"""

    # Kolory główne (Discord-like)
    BG_SIDEBAR = "#1e1f22"      # Lewa kolumna (serwery) - najciemniejszy
    BG_SECONDARY = "#2b2d31"    # Środkowa kolumna (kanały)
    BG_MAIN = "#313338"         # Header i akcenty
    BG_RIGHT = "#313338"        # Prawa kolumna (czat)

    # Kolory tekstu
    TEXT_PRIMARY = "#f2f3f5"    # Biały
    TEXT_SECONDARY = "#b5bac1"  # Szary
    TEXT_LABEL = "#f2f3f5"      # Białe labele
    TEXT_INPUT = "#dcddde"      # Tekst w inputach

    # Kolory inputów
    INPUT_BG = "#383a40"        # Tło inputu
    INPUT_BORDER = "#1e1f22"    # Border inputu

    # Kolory przycisków
    BUTTON_PRIMARY = "#ff4444"         # Czerwony (Voxen primary)
    BUTTON_PRIMARY_HOVER = "#ff6666"   # Jaśniejszy czerwony
    BUTTON_SECONDARY = "#4752c4"       # Niebieski (Discord-like)
    BUTTON_ADD = "#3ba55d"             # Zielony (Discord "Dodaj")

    # Kolory statusów
    ONLINE = "#3ba55d"          # Zielony
    IDLE = "#faa81a"            # Żółty
    DND = "#ed4245"             # Czerwony
    OFFLINE = "#80848e"         # Szary

    # Kolory dodatkowe (Voxen)
    ICON_COLOR = "#ff6b35"      # Pomarańczowy dla ikon
    BG_LEFT = "#1e1f22"         # Tło lewego panelu (login)
    ERROR = "#ff4444"           # Czerwony dla błędów
    SUCCESS = "#3ba55d"         # Zielony dla sukcesu


class Fonts:
    """Klasa zawierająca definicje czcionek"""

    FAMILY = "Segoe UI"  # lub "Arial", "Helvetica"

    # Rozmiary czcionek
    TITLE = (FAMILY, 32, "bold")
    TITLE_SMALL = ("Segoe UI", 16, "bold")
    SUBTITLE = (FAMILY, 14)
    LABEL = (FAMILY, 13, "bold")
    ICON = (FAMILY, 18)          # Zwiększony rozmiar dla ikon
    INPUT = (FAMILY, 14)
    BUTTON = (FAMILY, 15, "bold")
    MESSAGE = (FAMILY, 12)


class Dimensions:
    """Klasa zawierająca wymiary elementów"""

    # Wymiary okna
    WINDOW_WIDTH = 1080
    WINDOW_HEIGHT = 720

    # Wymiary pól input
    INPUT_WIDTH = 320
    INPUT_HEIGHT = 45

    # Wymiary przycisków
    BUTTON_WIDTH = 320
    BUTTON_HEIGHT = 45

    # Zaokrąglenia rogów
    CORNER_RADIUS = 6
    BUTTON_CORNER_RADIUS = 4

    # Odstępy
    PADDING_LARGE = 25
    PADDING_MEDIUM = 15
    PADDING_SMALL = 10

    SERVERS_WIDTH = 72      # Lewa kolumna (ikony serwerów)
    CHANNELS_WIDTH = 240    # Środkowa kolumna (lista kanałów)


class Config:
    """Ogólna konfiguracja aplikacji"""

    APP_TITLE = "Voxen v0.0.1 - alpha"
    APPEARANCE_MODE = "dark"      # "dark", "light", "system"
    COLOR_THEME = "dark-blue"          # "blue", "dark-blue", "green"
