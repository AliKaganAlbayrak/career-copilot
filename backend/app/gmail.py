"""Gmail bağlantısı: Google OAuth akışı ve Gmail sağlayıcısı.

Google'ın resmi kütüphaneleri yerine doğrudan REST uç noktalarını httpx ile
çağırıyoruz: bağımlılık az, akış görünür ve testlerde httpx.MockTransport ile
Google'ın yanıtları birebir taklit edilebiliyor.

Akış:
1. Kullanıcı "Gmail'i bağla" der -> authorization_url ile Google'ın izin sayfasına gider.
2. Google, ?code=...&state=... ile callback adresimize döner.
3. exchange_code ile kod, süresiz bir yenileme anahtarına (refresh token) çevrilir.
4. Her taramada access_token ile yenileme anahtarından kısa ömürlü erişim anahtarı alınır.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import httpx

from . import models
from .mail import MailAuthError, MailFetchError, MailMessage

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
# Yalnızca okuma izni: uygulama e-posta gönderemez, silemez, değiştiremez.
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
MAX_MESSAGES = 50  # tek taramada en fazla bu kadar ileti indirilir
BODY_LIMIT = 4000  # sınıflandırıcıya giden metin üst sınırı


@dataclass(frozen=True)
class GoogleSettings:
    client_id: str
    client_secret: str
    redirect_uri: str

    @classmethod
    def from_env(cls) -> GoogleSettings | None:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return None
        redirect = os.getenv(
            "GOOGLE_REDIRECT_URI", "http://localhost:8000/inbox/gmail/callback"
        ).strip()
        return cls(client_id, client_secret, redirect)


class GoogleOAuth:
    """Google OAuth 2.0 istemcisi (web sunucusu akışı)."""

    def __init__(self, settings: GoogleSettings, http: httpx.Client | None = None) -> None:
        self.settings = settings
        self.http = http or httpx.Client(timeout=20.0)

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            # offline + consent: Google yenileme anahtarını yalnızca böyle verir.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def _token_request(self, data: dict[str, str]) -> dict:
        try:
            response = self.http.post(TOKEN_URL, data=data)
        except httpx.HTTPError as exc:
            raise MailFetchError(f"Google'a ulaşılamadı: {exc}") from exc
        if response.status_code in (400, 401):
            # invalid_grant: kod kullanılmış, izin geri alınmış ya da süresi dolmuş.
            try:
                reason = str(response.json().get("error", "invalid_grant"))
            except ValueError:
                reason = "invalid_grant"
            raise MailAuthError(reason)
        if response.is_error:
            raise MailFetchError(f"Google beklenmedik yanıt verdi ({response.status_code}).")
        return response.json()

    def exchange_code(self, code: str) -> str:
        """İzin kodunu yenileme anahtarına çevirir."""
        data = self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "redirect_uri": self.settings.redirect_uri,
            }
        )
        refresh = data.get("refresh_token")
        if not refresh:
            raise MailAuthError("Google yenileme anahtarı vermedi.")
        return str(refresh)

    def access_token(self, refresh_token: str) -> str:
        """Yenileme anahtarından kısa ömürlü (yaklaşık 1 saat) erişim anahtarı alır."""
        data = self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
            }
        )
        return str(data["access_token"])

    def revoke(self, refresh_token: str) -> None:
        """İzni Google tarafında da geri alır. Başarısız olursa sessizce geçer:
        bağlantıyı bizim tarafta silmek her durumda yapılmalı."""
        try:
            self.http.post(REVOKE_URL, data={"token": refresh_token})
        except httpx.HTTPError:
            pass

    def profile_email(self, access_token: str) -> str:
        """Bağlanan Gmail hesabının adresi."""
        data = _gmail_get(self.http, "/profile", access_token)
        return str(data.get("emailAddress", ""))


def _gmail_get(http: httpx.Client, path: str, access_token: str, **params: object) -> dict:
    try:
        response = http.get(
            f"{GMAIL_API}{path}",
            params=params or None,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    except httpx.HTTPError as exc:
        raise MailFetchError(f"Gmail'e ulaşılamadı: {exc}") from exc
    if response.status_code == 401:
        raise MailAuthError("Gmail erişimi reddedildi.")
    if response.is_error:
        raise MailFetchError(f"Gmail beklenmedik yanıt verdi ({response.status_code}).")
    return response.json()


def _decode_base64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _find_part(payload: dict, mime: str) -> str | None:
    """Çok parçalı iletide istenen türdeki ilk gövdeyi bulur (iç içe parçalar dahil)."""
    if payload.get("mimeType") == mime and payload.get("body", {}).get("data"):
        return _decode_base64url(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        found = _find_part(part, mime)
        if found:
            return found
    return None


def extract_body(payload: dict, snippet: str = "") -> str:
    """Düz metin gövde; yoksa etiketleri temizlenmiş HTML; o da yoksa önizleme."""
    text = _find_part(payload, "text/plain")
    if text is None:
        html = _find_part(payload, "text/html")
        if html is not None:
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
    text = text if text is not None else snippet
    return re.sub(r"\s+", " ", text).strip()[:BODY_LIMIT]


def parse_message(data: dict) -> MailMessage:
    """Gmail API'nin ileti nesnesini sağlayıcıdan bağımsız MailMessage'a çevirir."""
    payload = data.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    received: datetime
    if data.get("internalDate"):
        received = datetime.fromtimestamp(int(data["internalDate"]) / 1000, tz=timezone.utc)
    else:
        try:
            received = parsedate_to_datetime(headers.get("date", ""))
        except (TypeError, ValueError):
            received = datetime.now(timezone.utc)

    return MailMessage(
        provider_id=str(data["id"]),
        sender=headers.get("from", ""),
        subject=headers.get("subject", "(konusuz)"),
        received_at=received,
        body=extract_body(payload, data.get("snippet", "")),
    )


class GmailProvider:
    """MailProvider arayüzünü Gmail API ile uygular."""

    def __init__(self, oauth: GoogleOAuth, refresh_token: str) -> None:
        self.oauth = oauth
        self.refresh_token = refresh_token

    def fetch_recent(
        self,
        user: models.User,
        days: int,
        known_ids: frozenset[str] = frozenset(),
    ) -> list[MailMessage]:
        token = self.oauth.access_token(self.refresh_token)
        listing = _gmail_get(
            self.oauth.http,
            "/messages",
            token,
            # Sohbetler, spam ve çöp kutusu dışında kalan son N günün iletileri.
            q=f"newer_than:{days}d -in:chats",
            maxResults=MAX_MESSAGES,
        )
        messages = []
        for item in listing.get("messages", []) or []:
            if item["id"] in known_ids:
                continue  # daha önce işlendi; yeniden indirme
            data = _gmail_get(self.oauth.http, f"/messages/{item['id']}", token, format="full")
            messages.append(parse_message(data))
        return messages


def get_google_oauth() -> GoogleOAuth | None:
    """FastAPI bağımlılığı: Google ayarları yoksa None (Gmail kapalı)."""
    settings = GoogleSettings.from_env()
    return GoogleOAuth(settings) if settings else None
