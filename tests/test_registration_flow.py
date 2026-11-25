"""
TEST - REGISTRATION FLOW & SIGN-UP GUI LOGIC
Weryfikacja: przełączania trybów Login/Register, walidacji formularza,
rejestracji w SQLite ze scrypt i natychmiastowego logowania.
"""

import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import customtkinter as ctk

from models.auth_model import AuthModel
from views.login_view import LoginView
from controllers.login_controller import LoginController


class MockApp:
    """Mock głównej aplikacji App do testów jednostkowych"""
    def __init__(self):
        self.logged_in_user = None

    def show_main_app(self, user_data):
        self.logged_in_user = user_data


def test_registration_and_toggle_flow():
    print("=== TEST REJESTRACJI NOWYCH KONT I FORMULARZA SIGN-UP ===")
    test_db = "test_registration.db"

    # Czyszczenie bazy testowej
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm", ".voxen_session"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass

    root = ctk.CTk()
    root.geometry("800x600")
    root.withdraw()

    model = AuthModel(db_path=test_db)
    view = LoginView(root)
    app = MockApp()
    controller = LoginController(model, view, app)
    view.set_controller(controller)

    # 1. Sprawdzenie stanu początkowego (Tryb Logowania)
    print(" [1/5] Sprawdzenie początkowego trybu formularza...")
    assert view.mode == LoginView.MODE_LOGIN
    assert view.title_label.cget("text") == "Witamy ponownie!"
    print(" [OK] Domyślny tryb to logowanie: SUKCES")

    # 2. Przełączenie na tryb Rejestracji
    print(" [2/5] Przełączenie na tryb Rejestracji (Sign-up)...")
    view.set_mode(LoginView.MODE_REGISTER)
    assert view.mode == LoginView.MODE_REGISTER
    assert view.title_label.cget("text") == "Stwórz konto"
    assert view.submit_button.cget("text") == "Zarejestruj się"
    print(" [OK] Przełączenie UI na rejestrację: SUKCES")

    # 3. Test walidacji - niezgodność haseł
    print(" [3/5] Test walidacji formularza rejestracji (hasła nie są identyczne)...")
    view.username_entry.insert(0, "NowyUser")
    view.email_entry.insert(0, "nowy@voxen.dev")
    view.password_entry.insert(0, "haslo123")
    view.confirm_password_entry.insert(0, "inne_haslo")

    controller.handle_register()
    assert "nie są identyczne" in view.status_label.cget("text")
    print(f" [OK] Odrzucenie różnych haseł: SUKCES ({view.status_label.cget('text')})")

    # 4. Poprawna rejestracja nowego konta
    print(" [4/5] Poprawna rejestracja i natychmiastowe logowanie...")
    view.confirm_password_entry.delete(0, "end")
    view.confirm_password_entry.insert(0, "haslo123")

    controller.handle_register()
    assert app.logged_in_user is not None
    assert app.logged_in_user["email"] == "nowy@voxen.dev"
    assert app.logged_in_user["username"] == "NowyUser"
    print(f" [OK] Rejestracja i auto-login: SUKCES (Zalogowano: {app.logged_in_user['username']})")

    # 5. Próba ponownej rejestracji na ten sam email (unikalność)
    print(" [5/5] Weryfikacja unikalności adresu email...")
    app.logged_in_user = None
    controller.handle_register()
    assert "już istnieje" in view.status_label.cget("text")
    assert app.logged_in_user is None
    print(f" [OK] Blokada istniejącego emaila: SUKCES ({view.status_label.cget('text')})")

    # Sprzątanie
    root.destroy()
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm", ".voxen_session"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass

    print("\n=== WSZYSTKIE TESTY REJESTRACJI I SIGN-UP ZAKOŃCZONE SUKCESEM! ===")


if __name__ == "__main__":
    test_registration_and_toggle_flow()
