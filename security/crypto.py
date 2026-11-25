"""
VOXEN SECURITY ENGINE - CRYPTO & PASSWORD HASHING
Zarządzanie kryptografią haseł, soleniem i odpornością na ataki czasowe (Timing Attacks).
Zgodne ze standardami NIST / OWASP z wykorzystaniem pamięciochłonnej funkcji scrypt (RFC 7914).
"""

import base64
import hashlib
import hmac
import os
import secrets
from typing import Tuple


class PasswordHasher:
    """
    Silnik haszowania haseł oparty na scrypt (pamięciochłonny, odporny na GPU/ASIC).
    Parametry:
    - N = 16384 (koszt procesora/pamięci)
    - r = 8 (rozmiar bloku)
    - p = 1 (równoległość)
    - Długość soli: 32 bajty (256 bitów)
    """

    SCRYPT_N = 16384
    SCRYPT_R = 8
    SCRYPT_P = 1
    SALT_BYTES = 32
    KEY_LENGTH = 64

    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Generuje bezpieczną sól kryptograficzną i hasz scrypt.
        Zwraca string w standardowym formacie modułowym:
        $scrypt$N=16384,r=8,p=1$<b64_salt>$<b64_hash>
        """
        if not password:
            raise ValueError("Hasło nie może być puste.")

        salt = secrets.token_bytes(cls.SALT_BYTES)
        derived_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=cls.SCRYPT_N,
            r=cls.SCRYPT_R,
            p=cls.SCRYPT_P,
            maxmem=32 * 1024 * 1024,
            dklen=cls.KEY_LENGTH
        )

        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(derived_key).decode("ascii")

        return f"$scrypt$N={cls.SCRYPT_N},r={cls.SCRYPT_R},p={cls.SCRYPT_P}${salt_b64}${hash_b64}"

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        """
        Weryfikuje hasło względem zapisanego hasza.
        Używa hmac.compare_digest (porównanie w czasie stałym) dla eliminacji Timing Attacks.
        """
        if not password or not stored_hash:
            return False

        try:
            parts = stored_hash.split("$")
            # Format: ['', 'scrypt', 'N=16384,r=8,p=1', '<salt>', '<hash>']
            if len(parts) != 5 or parts[1] != "scrypt":
                return False

            params_str = parts[2]
            params = dict(param.split("=") for param in params_str.split(","))
            n = int(params.get("N", cls.SCRYPT_N))
            r = int(params.get("r", cls.SCRYPT_R))
            p = int(params.get("p", cls.SCRYPT_P))

            salt = base64.b64decode(parts[3].encode("ascii"))
            expected_key = base64.b64decode(parts[4].encode("ascii"))

            computed_key = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                maxmem=32 * 1024 * 1024,
                dklen=len(expected_key)
            )

            # Bezpieczne porównanie stałoczasowe
            return hmac.compare_digest(computed_key, expected_key)

        except Exception:
            return False
