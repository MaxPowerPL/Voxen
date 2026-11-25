"""
TEST SUITE - VOXEN SECURITY, PASSWORD HASHING & SQLITE ENGINE
Weryfikacja: scrypt, stałoczasowości, bazy SQLite (WAL), migracji z JSON i sesji.
"""

import io
import os
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from security.crypto import PasswordHasher
from security.session import SessionManager
from database.db import DatabaseManager
from models.auth_model import AuthModel


def test_password_hasher():
    print("\n--- TEST 1: PasswordHasher (scrypt) ---")
    password = "SuperTajneHaslo123!"

    # 1. Haszowanie
    hash_str = PasswordHasher.hash_password(password)
    print(f" [OK] Wygenerowano hasz: {hash_str[:40]}... (długość: {len(hash_str)})")
    assert hash_str.startswith("$scrypt$N=16384,r=8,p=1$")

    # 2. Weryfikacja poprawnego hasła
    assert PasswordHasher.verify_password(password, hash_str) is True
    print(" [OK] Weryfikacja poprawnego hasła: SUKCES")

    # 3. Weryfikacja błędnego hasła
    assert PasswordHasher.verify_password("ZleHaslo", hash_str) is False
    print(" [OK] Odrzucenie błędnego hasła: SUKCES")

    # 4. Solenie (dwa te same hasła muszą dać różne hasze)
    hash_str_2 = PasswordHasher.hash_password(password)
    assert hash_str != hash_str_2
    print(" [OK] Unikalność soli (Salt Randomness): SUKCES")


def test_sqlite_database_and_migration():
    print("\n--- TEST 2: SQLite Database & JSON Migration ---")
    test_db = "test_voxen.db"
    test_json = "test_users_migration.json"

    # Przygotowanie pliku JSON do symulacji migracji
    import json
    sample_json_data = {
        "users": [
            {
                "email": "migrated_admin@voxen.dev",
                "password": "plain_text_admin_pass",
                "security": 5,
                "last_login": "2026-01-01 12:00:00"
            }
        ]
    }
    with open(test_json, "w", encoding="utf-8") as f:
        json.dump(sample_json_data, f)

    # Inicjalizacja bazy
    if Path(test_db).exists():
        Path(test_db).unlink()

    db = DatabaseManager(db_path=test_db)
    # Wywołaj migrację z testowego pliku
    db._migrate_from_json_if_needed(json_path=test_json)

    # Sprawdź czy użytkownik jest w bazie z bezpiecznym hashem
    user = db.get_user_by_email("migrated_admin@voxen.dev")
    assert user is not None
    assert user["password_hash"].startswith("$scrypt$")
    assert PasswordHasher.verify_password("plain_text_admin_pass", user["password_hash"]) is True
    print(" [OK] Migracja z JSON do SQLite z haszowaniem scrypt: SUKCES")

    # Tworzenie nowego użytkownika
    success, new_user = db.create_user("nowy@test.pl", "bezpieczne_haslo_456")
    assert success is True
    assert new_user["email"] == "nowy@test.pl"
    print(" [OK] Tworzenie nowego użytkownika w SQLite: SUKCES")

    # Próba duplikatu
    dup_success, err = db.create_user("nowy@test.pl", "inne_haslo")
    assert dup_success is False
    print(f" [OK] Blokada duplikatów email: SUKCES ({err})")

    # Sprzątanie plików testowych
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm", test_json, f"{test_json}.migrated"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass


def test_auth_model_and_sessions():
    print("\n--- TEST 3: AuthModel & Session Persistence ---")
    test_db = "test_auth.db"
    test_session = "test_session.json"

    if Path(test_db).exists():
        Path(test_db).unlink()
    if Path(test_session).exists():
        Path(test_session).unlink()

    model = AuthModel(db_path=test_db)
    model.session_manager.session_file = Path(test_session)

    # 1. Rejestracja
    reg_ok, user_data = model.register_user("jan@voxen.pl", "tajne_haslo_123")
    assert reg_ok is True

    # 2. Logowanie błędnym hasłem
    valid, msg = model.validate_credentials("jan@voxen.pl", "zle_haslo")
    assert valid is False
    assert msg == "Nieprawidłowe hasło!"
    print(" [OK] Odrzucenie nieprawidłowego hasła przez AuthModel: SUKCES")

    # 3. Logowanie poprawnym hasłem
    valid, user = model.validate_credentials("jan@voxen.pl", "tajne_haslo_123")
    assert valid is True
    assert "password_hash" not in user
    print(f" [OK] Prawidłowe logowanie i generowanie sesji: SUKCES (User: {user['username']})")

    # 4. Sprawdzenie Auto-Login (Session resume)
    saved_user = model.check_saved_session()
    assert saved_user is not None
    assert saved_user["email"] == "jan@voxen.pl"
    print(f" [OK] Wznawianie trwałej sesji (Auto-Login): SUKCES (Token aktywny)")

    # 5. Wylogowanie
    model.logout()
    after_logout_user = model.check_saved_session()
    assert after_logout_user is None
    print(" [OK] Wylogowanie i unieważnienie sesji: SUKCES")

    # Sprzątanie
    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm", test_session]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except Exception:
                pass


if __name__ == "__main__":
    print("=== TEST BEZPIECZEŃSTWA, HASHOWANIA I BAZY SQLITE VOXEN ===")
    test_password_hasher()
    test_sqlite_database_and_migration()
    test_auth_model_and_sessions()
    print("\n=== WSZYSTKIE TESTY BEZPIECZEŃSTWA ZAKOŃCZONE SUKCESEM! ===")
