"""
CONTROLLER - Obsługa logiki aplikacji i komunikacji między Model a View
"""
from models.auth_model import AuthModel


class LoginController:
    """Controller ekranu logowania (Controller w MVC)"""

    def __init__(self, model, view, app):
        """
        Inicjalizacja controllera

        Args:
            model: Instancja AuthModel
            view: Instancja LoginView
            app: Instancja głównej aplikacji (dla przełączania widoków)
        """
        self.model = model
        self.view = view
        self.app = app
        self.current_user = None

    def handle_login(self):
        """
        Obsługuje proces logowania.
        Może być wywołana przez:
        - Kliknięcie przycisku myszką
        - Naciśnięcie Enter w formularzu
        - Inne zdarzenia UI
        """
        # Pobierz dane z widoku
        email, password = self.view.get_credentials()

        # Zwaliduj dane używając modelu
        success, result = self.model.validate_credentials(email, password)

        if success:
            # Logowanie udane
            user_data = result
            self.current_user = user_data

            # Zaktualizuj datę logowania w modelu
            self.model.update_last_login(email)

            # Przejdź do głównego ekranu aplikacji
            self._on_login_success(user_data)
        else:
            # Logowanie nieudane - wyświetl błąd przez View
            self.view.show_error(result)

    def _on_login_success(self, user_data):
        """
        Wywołane po udanym logowaniu

        Args:
            user_data: Dane zalogowanego użytkownika
        """
        print(f"Zalogowano: {user_data['email']}")
        print(f"Poziom uprawnień: {user_data.get('security', 0)}")
        print(f"Ostatnie logowanie: {user_data.get('last_login', 'Nigdy')}")

        # Poinformuj główną aplikację o udanym logowaniu
        self.app.show_main_app(user_data)

    def get_current_user(self):
        """
        Zwraca dane aktualnie zalogowanego użytkownika

        Returns:
            dict: Dane użytkownika lub None
        """
        return self.current_user
