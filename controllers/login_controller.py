"""
CONTROLLER - Obsługa logiki autentykacji, logowania i rejestracji (MVC Controller)
"""

from typing import Optional
from models.auth_model import AuthModel


class LoginController:
    """Controller ekranu logowania i rejestracji (Controller w MVC)"""

    def __init__(self, model: AuthModel, view, app):
        """
        Inicjalizacja controllera

        Args:
            model: Instancja AuthModel (SQLite + scrypt)
            view: Instancja LoginView
            app: Instancja głównej aplikacji (App)
        """
        self.model = model
        self.view = view
        self.app = app
        self.current_user = None

    def handle_login(self):
        """Obsługuje proces logowania użytkownika"""
        email, password = self.view.get_login_credentials()

        if not email or not password:
            self.view.show_error("Wypełnij wszystkie pola!")
            return

        success, result = self.model.validate_credentials(email, password)

        if success:
            user_data = result
            self.current_user = user_data
            self.model.update_last_login(email)
            self._on_login_success(user_data)
        else:
            self.view.show_error(result)

    def handle_register(self):
        """Obsługuje proces rejestracji nowego konta"""
        username, email, password, confirm_password = self.view.get_register_credentials()

        # 1. Walidacja danych wejściowych
        if not username or not email or not password or not confirm_password:
            self.view.show_error("Wypełnij wszystkie pola!")
            return

        if len(username) < 3:
            self.view.show_error("Nazwa użytkownika musi mieć co najmniej 3 znaki!")
            return

        if "@" not in email or "." not in email:
            self.view.show_error("Podaj poprawny adres email!")
            return

        if len(password) < 6:
            self.view.show_error("Hasło musi mieć co najmniej 6 znaków!")
            return

        if password != confirm_password:
            self.view.show_error("Hasła nie są identyczne!")
            return

        # 2. Zapis w bazie SQLite z bezpiecznym haszowaniem scrypt
        success, result = self.model.register_user(
            email=email,
            password=password,
            username=username
        )

        if success:
            # 3. Pomyślna rejestracja -> natychmiastowe utworzenie sesji i auto-login
            print(f"Pomyślnie zarejestrowano konto: {email} ({username})")
            _, user_data = self.model.validate_credentials(email, password)
            self._on_login_success(user_data)
        else:
            self.view.show_error(str(result))

    def _on_login_success(self, user_data: dict):
        """Wywoływane po pomyślnym logowaniu lub rejestracji"""
        print(f"Zalogowano pomyślnie: {user_data.get('email')} (Rola: {user_data.get('security', 1)})")
        self.app.show_main_app(user_data)

    def get_current_user(self) -> Optional[dict]:
        """Zwraca dane aktualnego użytkownika"""
        return self.current_user
