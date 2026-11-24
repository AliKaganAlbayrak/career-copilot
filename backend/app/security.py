"""Parola özetleme ve JWT (erişim belirteci) yardımcıları.

Parolalar asla düz metin saklanmaz. Standart kütüphanedeki scrypt ile,
her kullanıcıya özel rastgele bir "tuz" (salt) eklenerek özetlenir.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

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
    payload = {"sub": str(user_id), "purpose": "access", "exp": expires_at}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Belirteç geçerliyse kullanıcı kimliğini, değilse None döndürür."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Aynı anahtarla imzalanan başka belirteçler (ör. OAuth state) URL'de
        # dolaşır; onlar oturum açmak için kullanılamasın.
        if payload.get("purpose") != "access":
            return None
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# --- Saklanan gizli değerlerin şifrelenmesi ---
#
# Gmail'in yenileme anahtarı (refresh token), posta kutusuna süresiz okuma
# erişimi verir. Veritabanı sızarsa bu anahtarlar işe yaramasın diye düz metin
# değil, Fernet (AES + HMAC) ile şifrelenmiş saklanır.


def _fernet() -> Fernet:
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        # Ayrı anahtar verilmemişse SECRET_KEY'den 32 baytlık anahtar türet.
        digest = hashlib.sha256(f"token-sifreleme:{SECRET_KEY}".encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str | None:
    """Şifreyi çözer; anahtar değişmiş ya da veri bozulmuşsa None döndürür."""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


# --- OAuth "state" belirteci ---
#
# Google girişten dönerken tarayıcı bizim API'mize Authorization başlığı
# taşımaz; hangi kullanıcının döndüğünü state parametresinden anlarız.
# State imzalı ve 10 dakikalık olduğu için sahtesi üretilemez (CSRF koruması).

_STATE_PURPOSE = "gmail-oauth"


def create_state_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": _STATE_PURPOSE,
        "nonce": secrets.token_urlsafe(8),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_state_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != _STATE_PURPOSE:
            return None  # erişim belirteci state yerine kullanılamasın
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
