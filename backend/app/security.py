"""Parola özetleme ve JWT (erişim belirteci) yardımcıları.

Parolalar asla düz metin saklanmaz. Standart kütüphanedeki scrypt ile,
her kullanıcıya özel rastgele bir "tuz" (salt) eklenerek özetlenir.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

# Geliştirme için varsayılan anahtar; üretimde SECRET_KEY ortam değişkeni şart.
SECRET_KEY = os.getenv("SECRET_KEY", "gelistirme-anahtari-uretimde-mutlaka-degistir")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# scrypt maliyet parametreleri: kaba kuvvet denemelerini pahalı kılar.
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    """Parolayı 'tuz$özet' biçiminde saklanabilir metne çevirir."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Girilen parolanın saklanan özetle eşleşip eşleşmediğini söyler."""
    try:
        salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False

    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    # compare_digest: zamanlama saldırılarına karşı sabit süreli karşılaştırma.
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_access_token(user_id: int) -> str:
    """Kullanıcı kimliğini taşıyan, süresi dolan imzalı bir JWT üretir."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Belirteç geçerliyse kullanıcı kimliğini, değilse None döndürür."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
