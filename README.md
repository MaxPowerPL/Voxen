<div align="center">

  <img src="assets/images/logo.ico" alt="Voxen Logo" width="200" height="auto" />

  # Voxen

  **Nowoczesny komunikator inspirowany Discordem zbudowany w Pythonie**
  <br>
  *Szybka, elegancka komunikacja z interfejsem opartym na MVC*

  <p>
    <a href="https://github.com/MaxPowerPL/Voxen/releases/tag/v0.0.1-alpha">
      <img src="https://img.shields.io/github/v/tag/MaxPowerPL/Voxen?label=VERSION&style=for-the-badge&color=238636" alt="Wersja" />
    </a>
    <a href="#">
      <img src="https://img.shields.io/badge/Status-Alpha-important?style=for-the-badge" alt="Status" />
    </a>
    <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    </a>
    <a href="https://customtkinter.tomschimansky.com/">
      <img src="https://img.shields.io/badge/CustomTkinter-5.2.0-FF5722?style=for-the-badge&logo=python&logoColor=white" alt="CustomTkinter" />
    </a>
    <a href="https://github.com/MaxPowerPL/Voxen/stargazers">
      <img src="https://img.shields.io/github/stars/MaxPowerPL/Voxen?style=for-the-badge&color=yellow" alt="Stars" />
    </a>
    <a href="https://github.com/MaxPowerPL/Voxen">
      <img src="https://img.shields.io/github/last-commit/MaxPowerPL/Voxen?style=for-the-badge" alt="Last Commit" />
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/License-Custom%20Proprietary-green?style=for-the-badge" alt="License" />
    </a>
  </p>

  <p>
    <a href="#-o-projekcie">📖 O Projekcie</a> •
    <a href="#-funkcjonalności">✨ Funkcjonalności</a> •
    <a href="#-instalacja-i-uruchomienie">🚀 Instalacja</a> •
    <a href="#-struktura-projektu">📂 Struktura</a> •
    <a href="#%EF%B8%8F-roadmapa">🗺️ Roadmapa</a>
  </p>
</div>

---

## 📖 O Projekcie

Voxen to nowoczesny komunikator instant messaging stworzony w Pythonie, inspirowany estetyką i funkcjonalnością Discorda. Projekt powstał jako demonstracja zaawansowanych technik programowania GUI oraz implementacji wzorca architektonicznego Model-View-Controller (MVC) w aplikacjach desktopowych.

Aplikacja wykorzystuje CustomTkinter do stworzenia eleganckiego, ciemnego interfejsu użytkownika z płynną animacją, dynamicznym skalowaniem obrazków oraz responsywnym layoutem przypominającym popularne komunikatory. Voxen obsługuje autentykację użytkowników z walidacją danych, zarządzanie kontaktami i serwerami, statusy online/offline oraz przygotowany jest pod rozbudowę o funkcje czatu w czasie rzeczywistym.

### 🎯 Aktualna Wersja: `v0.0.1 (Alpha)`
Pierwsza publiczna wersja alfa zawiera kompletny system logowania z walidacją, główny interfejs z trzema kolumnami (serwery, kanały, czat), wsparcie dla statusów użytkownika oraz podstawową strukturę UI gotową pod implementację WebSocket dla komunikacji real-time. System jest w pełni funkcjonalny jako frontend z przykładowymi danymi.

---

## ✨ Funkcjonalności

Co już działa w tej wersji?

- [x] **System Logowania**:
  - Walidacja email i hasła: Sprawdzanie formatu oraz zgodności danych z bazą JSON.
  - Obsługa błędów: Komunikaty o błędnych danych wyświetlane w czasie rzeczywistym.
  - Binding klawiatury: Enter w polu email przenosi fokus na hasło, Enter w haśle loguje.
- [x] **Interfejs w Stylu Discord**:
  - Trzy kolumny: Serwery (72px), kanały/konwersacje (240px), obszar czatu (elastyczny).
  - Okrągłe przyciski serwerów: Z emoji lub custom logo, dynamiczny hover effect.
  - Lista konwersacji: Z avatarami, statusami (online/idle/dnd/offline) i wskaźnikiem aktywności.
- [x] **MVC Architecture**:
  - Model (auth_model.py): Zarządzanie danymi użytkowników w JSON.
  - View (login_view.py, app_view.py): Warstwa prezentacji z CustomTkinter.
  - Controller (login_controller.py): Logika biznesowa i komunikacja między Model-View.
- [ ] **Chat Real-Time** (W przygotowaniu):
  - WebSocket connection: Integracja z serwerem do komunikacji w czasie rzeczywistym.

---

## 🛠️ Technologie

Projekt został zbudowany przy użyciu:

| Technologia | Opis |
| :--- | :--- |
| **Python 3.14+** | Główny język programowania, wykorzystujący nowoczesne funkcje typu hints i match-case. |
| **CustomTkinter 5.2.0** | Framework GUI oparty na Tkinter z nowoczesnym, ciemnym designem i płynną animacją. |
| **Pillow (PIL)** | Biblioteka do przetwarzania obrazów - skalowanie, maskowanie okrągłe, dynamic resize. |
| **JSON** | Format przechowywania danych użytkowników (tymczasowa baza przed integracją z API). |

---

## 🚀 Instalacja i Uruchomienie

Aby uruchomić projekt na swoim komputerze, wykonaj następujące kroki:

### 1. Wymagania
- Python 3.14 lub nowszy
- pip (menedżer pakietów Python)
- System operacyjny: Windows, macOS lub Linux

### 2. Klonowanie repozytorium
```bash
git clone https://github.com/MaxPowerPL/Voxen
cd Voxen
```

### 3. Konfiguracja środowiska

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Instalacja zależności
```bash
pip install -r requirements.txt
```

**Alternatywnie (manualna instalacja):**
```bash
pip install customtkinter pillow
```

### 5. Uruchomienie
```bash
python main.py
```

### 6. Sterowanie
- **Logowanie**: Email: `admin@admin.pl`, Hasło: `admin123` (domyślne konto testowe).
- **Enter**: W polu email → przenosi fokus na hasło. W polu hasło → loguje.
- **Przyciski serwerów**: Kliknięcie wyświetla nazwę serwera w konsoli (TODO: ładowanie kanałów).
- **Lista kontaktów**: Kliknięcie otwiera konwersację (zmienia tytuł czatu).

---

## 📂 Struktura Projektu

Projekt wykorzystuje wzorzec **MVC (Model-View-Controller)** z wyraźnym podziałem odpowiedzialności między warstwy:

```text
📦 Voxen
┣ 📂 assets/
┃ ┣ 📂 images/
┃ ┃ ┣ 🖼️ logo.ico                # Ikona aplikacji (Windows taskbar)
┃ ┃ ┗ 🖼️ login_background.png    # Tło ekranu logowania
┣ 📂 controllers/
┃ ┗ 📜 login_controller.py       # Logika logowania (MVC Controller)
┣ 📂 models/
┃ ┗ 📜 auth_model.py             # Zarządzanie danymi użytkowników (MVC Model)
┣ 📂 views/
┃ ┣ 📜 login_view.py             # Ekran logowania (MVC View)
┃ ┗ 📜 app_view.py               # Główny ekran aplikacji (MVC View)
┣ 📜 main.py                     # Punkt wejścia - inicjalizacja aplikacji
┣ 📜 utils.py                    # Kolory, fonty, konfiguracja
┣ 📜 users.json                  # Baza użytkowników (generowana automatycznie)
┣ 📜 requirements.txt            # Zależności Python
┣ 📜 LICENSE                     # Licencja Custom Proprietary
┗ 📜 README.md
```

### Opis głównych modułów:

#### `controllers/`
| Plik | Opis |
|------|------|
| `login_controller.py` | Obsługuje logikę logowania: walidację credentials, komunikację z modelem, przełączanie widoków. |

#### `models/`
| Plik | Opis |
|------|------|
| `auth_model.py` | Zarządza danymi użytkowników w JSON: ładowanie, zapis, walidacja email/hasło, update last login. |

#### `views/`
| Plik | Opis |
|------|------|
| `login_view.py` | Interfejs ekranu logowania: formularz z email/hasło, dynamiczne tło, komunikaty błędów. |
| `app_view.py` | Główny ekran: 3 kolumny (serwery, kanały, czat), scrollable listy, user panel, status indicators. |

#### `utils.py`
Zawiera klasę `Colors` (paleta Discord-like), `Fonts` (Segoe UI typography), `Dimensions` (rozmiary UI), `Config` (ustawienia aplikacji).

---

## 🎨 Design System

Voxen wykorzystuje spójny system designu inspirowany Discordem:

### Paleta Kolorów:
- **Background**: `#1e1f22` (serwery) → `#2b2d31` (kanały) → `#313338` (czat) - gradient ciemności.
- **Primary Action**: `#ff4444` (czerwony Voxen) z hover `#ff6666`.
- **Secondary Action**: `#4752c4` (niebieski Discord) dla alternatywnych akcji.
- **Statusy**: `#3ba55d` (online), `#faa81a` (idle), `#ed4245` (dnd), `#80848e` (offline).

### Typografia:
1. **Segoe UI** - główna czcionka (native Windows look).
2. **Rozmiary** - Title (32px bold), Subtitle (14px), Label (13px bold), Input (14px).

---

## 🗺️ Roadmapa

Plany rozwoju projektu:

### Faza 1: Foundation (Ukończone ✅)
- [x] Implementacja wzorca MVC
- [x] System logowania z walidacją
- [x] Discord-like UI (3 kolumny, scrollable listy)
- [x] Responsywny layout z grid system

### Faza 2: Backend & Real-Time (W toku 🔧)
- [ ] WebSocket server (Python/FastAPI lub Node.js)
- [ ] Przesyłanie wiadomości w czasie rzeczywistym
- [ ] Baza danych (PostgreSQL/MongoDB) zamiast JSON
- [ ] Rejestracja użytkowników z hash hasła (bcrypt)

### Faza 3: Advanced Features (Planowane 📅)
- [ ] Tworzenie i zarządzanie serwerami
- [ ] Kanały tekstowe i głosowe (integracja WebRTC)
- [ ] Upload plików i obrazków
- [ ] Emoji picker i reakcje
- [ ] Powiadomienia desktop (Windows Toast)

---

## 🐛 Znane Problemy i Rozwiązania

### ✅ Naprawione w v0.0.1:
- **Padding w przyciskach**: Zamieniono CTkFrame na CTkButton z `corner_radius=24` - okrągłe przyciski działają perfekcyjnie.
- **Skalowanie tła**: Użyto `ImageOps.fit()` z LANCZOS resampling dla płynnego skalowania (CSS background-size: cover).

### 🔧 Do poprawy:
- [ ] Brak persystencji sesji (logout po zamknięciu aplikacji)
- [ ] Hasła przechowywane plain-text (wymaga hash bcrypt przed produkcją)
- [ ] Brak animacji przejść między widokami

---

## 📝 Changelog

### v0.0.1 (Alpha Release)
**NEW FEATURES:**
- System logowania MVC z walidacją email/hasło
- Główny interfejs Discord-like z 3 kolumnami
- Okrągłe przyciski serwerów z hover effect
- Lista konwersacji z statusami (online/idle/dnd/offline)
- User panel z avatarem i statusem

**Zmiany techniczne:**
- Implementacja wzorca MVC (separacja Model-View-Controller)
- Dynamic image scaling z PIL (ImageOps.fit)
- Keyboard bindings (Enter navigation)
- Grid-based responsive layout

---

## 📜 Licencja

Ten projekt jest udostępniony na **Własnej Licencji Zastrzeżonej (Custom Proprietary License)**.

### Co MOŻESZ robić:
- ✅ Przeglądać i studiować kod źródłowy w celach edukacyjnych
- ✅ Pobrać i uruchomić aplikację do użytku osobistego, niekomercyjnego
- ✅ Umieścić ten projekt w swoim portfolio lub CV
- ✅ Rekruterzy mogą przeglądać i testować kod podczas procesów rekrutacyjnych

### Czego NIE MOŻESZ robić bez zgody:
- ❌ Używać tego kodu komercyjnie lub w płatnych projektach
- ❌ Publikować lub dystrybuować zmodyfikowane wersje
- ❌ Umieszczać ten kod w innych publicznych repozytoriach
- ❌ Używać fragmentów kodu w aplikacjach komercyjnych

### Użytek komercyjny
Jeśli chcesz użyć tego oprogramowania komercyjnie lub opublikować modyfikacje, skontaktuj się ze mną: **dominik.kielczewski@gmail.com**

Zobacz pełne warunki prawne w pliku [LICENSE](LICENSE).

---

<div align="center">

### ⭐ Jeśli podoba Ci się ten projekt, zostaw gwiazdkę na GitHubie! ⭐

☕ Stworzono używając Python, CustomTkinter i miłości do cleancode.
<br>
<sub>Projekt edukacyjny demonstrujący wzorzec MVC w aplikacjach desktopowych.</sub>
<br>
<sub>**Licencja Zastrzeżona** - Kod jest widoczny tylko w celach edukacyjnych. Zobacz [LICENSE](LICENSE) po szczegóły.</sub>

<p>
  <a href="https://github.com/MaxPowerPL/Voxen/issues/new?labels=bug">🐛 Zgłoś Bug</a> •
  <a href="https://github.com/MaxPowerPL/Voxen/issues/new?labels=enhancement">💡 Zaproponuj Funkcję</a> •
  <a href="https://github.com/MaxPowerPL/Voxen/wiki">📖 Wiki</a>
</p>

![Status](https://img.shields.io/badge/Status-Alpha-brightgreen?style=for-the-badge&logo=statuspage&logoColor=white)

</div>
