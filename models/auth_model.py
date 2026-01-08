"""
MODEL - Zarządzanie danymi użytkowników i logika biznesowa autentykacji
"""
import json
from datetime import datetime
from pathlib import Path


class AuthModel:
    """Model zarządzający danymi użytkowników (Model w MVC)"""

    def __init__(self, json_file="users.json"):
        """
        Inicjalizacja modelu autentykacji

        Args:
            json_file: Ścieżka do pliku JSON z użytkownikami
        """
        self.json_file = Path(json_file)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Sprawdza czy plik JSON istnieje, jeśli nie - tworzy domyślny"""
        if not self.json_file.exists():
            default_data = {
                "users": [
                    {
                        "email": "admin@admin.pl",
                        "password": "admin123",
                        "security": 5,
                        "last_login": None
                    }
                ]
            }
            self._save_data(default_data)

    def _load_data(self):
        """
        Wczytuje dane z pliku JSON

        Returns:
            dict: Słownik z danymi użytkowników
        """
        try:
            with open(self.json_file, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Błąd wczytywania pliku JSON: {e}")
            return {"users": []}

    def _save_data(self, data):
        """
        Zapisuje dane do pliku JSON

        Args:
            data: Słownik z danymi do zapisania
        """
        try:
            with open(self.json_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Błąd zapisywania do pliku JSON: {e}")

    def validate_credentials(self, email, password):
        """
        Sprawdza poprawność danych logowania

        Args:
            email: Email użytkownika
            password: Hasło użytkownika

        Returns:
            tuple: (bool, dict/str) - (sukces, dane_użytkownika lub komunikat_błędu)
        """
        # Walidacja podstawowa
        if not email or not password:
            return False, "Wypełnij wszystkie pola!"

        if "@" not in email:
            return False, "Podaj poprawny adres email!"

        # Wczytaj dane
        data = self._load_data()

        # Szukaj użytkownika
        for user in data.get("users", []):
            if user["email"] == email:
                if user["password"] == password:
                    return True, user
                else:
                    return False, "Nieprawidłowe hasło!"

        return False, "Użytkownik nie istnieje!"

    def update_last_login(self, email):
        """
        Aktualizuje datę ostatniego logowania dla użytkownika

        Args:
            email: Email użytkownika
        """
        data = self._load_data()

        # Znajdź użytkownika i zaktualizuj datę
        for user in data.get("users", []):
            if user["email"] == email:
                user["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break

        # Zapisz zaktualizowane dane
        self._save_data(data)

    def get_user_info(self, email):
        """
        Pobiera informacje o użytkowniku

        Args:
            email: Email użytkownika

        Returns:
            dict: Dane użytkownika lub None
        """
        data = self._load_data()

        for user in data.get("users", []):
            if user["email"] == email:
                return user

        return None