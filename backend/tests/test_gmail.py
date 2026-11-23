"""Gmail bağlantısı. Google'ın sunucuları httpx.MockTransport ile taklit edilir:
testler internete çıkmaz ama istekler gerçek HTTP katmanından geçer."""

from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.gmail import GoogleOAuth, GoogleSettings, extract_body, get_google_oauth, parse_message
from app.llm import get_llm_client
from app.main import app
from app.security import create_state_token, decode_state_token


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


ILETILER = {
    "g1": {
        "id": "g1",
        "internalDate": "1795000000000",
        "snippet": "Sizi mülakata davet ediyoruz",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Aselsan İK <ik@aselsan.com.tr>"},
                {"name": "Subject", "value": "Mülakat daveti"},
            ],
            "parts": [
                {"mimeType": "text/html", "body": {"data": b64("<p>HTML sürüm</p>")}},
                {"mimeType": "text/plain", "body": {"data": b64("Sizi 25 Kasım'da mülakata davet ediyoruz.")}},
            ],
        },
    },
    "g2": {
        "id": "g2",
        "internalDate": "1795000100000",
        "snippet": "indirim",
        "payload": {
            "mimeType": "text/html",
            "headers": [
                {"name": "From", "value": "Mağaza <bulten@magaza.example>"},
                {"name": "Subject", "value": "Kampanya"},
            ],
            "body": {"data": b64("<style>p{}</style><p>Büyük <b>indirim</b></p>")},
        },
    },
}


class SahteGoogle:
    """Google OAuth ve Gmail uç noktalarını taklit eder, gelen istekleri kaydeder."""

    def __init__(self) -> None:
        self.istekler: list[httpx.Request] = []
        self.iptal_edilen: list[str] = []
        self.izin_gecersiz = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.istekler.append(request)
        url = request.url
        if url.host == "oauth2.googleapis.com" and url.path == "/token":
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["authorization_code"]:
                if form["code"] != ["gecerli-kod"]:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                return httpx.Response(200, json={"access_token": "erisim-1", "refresh_token": "yenileme-1"})
            if self.izin_gecersiz:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "erisim-2", "expires_in": 3599})
        if url.host == "oauth2.googleapis.com" and url.path == "/revoke":
            self.iptal_edilen.append(parse_qs(request.content.decode())["token"][0])
            return httpx.Response(200)
        if url.host == "gmail.googleapis.com":
            assert request.headers["Authorization"].startswith("Bearer erisim-")
            yol = url.path.removeprefix("/gmail/v1/users/me")
            if yol == "/profile":
                return httpx.Response(200, json={"emailAddress": "ali@gmail.com"})
            if yol == "/messages":
                return httpx.Response(200, json={"messages": [{"id": "g1"}, {"id": "g2"}]})
            if yol.startswith("/messages/"):
                return httpx.Response(200, json=ILETILER[yol.split("/")[-1]])
        return httpx.Response(404)

    def indirilen_iletiler(self) -> list[str]:
        return [r.url.path.split("/")[-1] for r in self.istekler if "/messages/" in r.url.path]


@pytest.fixture()
def google(auth_client):
    sahte = SahteGoogle()
    oauth = GoogleOAuth(
        GoogleSettings("istemci", "gizli", "http://localhost:8000/inbox/gmail/callback"),
        http=httpx.Client(transport=httpx.MockTransport(sahte)),
    )
    app.dependency_overrides[get_google_oauth] = lambda: oauth
    return sahte


class SahteLLM:
    def generate(self, prompt: str, *, system: str, json_mode: bool = False) -> str:
        return json.dumps(
            {"is_job_related": True, "category": "mulakat_daveti", "company": "Aselsan",
             "summary": "25 Kasım'da mülakata davet ediliyorsun."}
        )


def bagla(client) -> httpx.Response:
    """Bağlama akışının tamamı: izin adresini al, Google'ın dönüşünü taklit et."""
    auth_url = client.get("/inbox/gmail/connect").json()["auth_url"]
    state = parse_qs(urlparse(auth_url).query)["state"][0]
    return client.get(
        "/inbox/gmail/callback",
        params={"code": "gecerli-kod", "state": state},
        follow_redirects=False,
    )


# --- Saf işlevler ---

def test_duz_metin_htmlden_once_secilir():
    mesaj = parse_message(ILETILER["g1"])

    assert mesaj.sender == "Aselsan İK <ik@aselsan.com.tr>"
    assert mesaj.subject == "Mülakat daveti"
    assert mesaj.body == "Sizi 25 Kasım'da mülakata davet ediyoruz."
    assert mesaj.received_at.year == 2026


def test_yalniz_html_varsa_etiketler_temizlenir():
    assert extract_body(ILETILER["g2"]["payload"]) == "Büyük indirim"


def test_govde_yoksa_onizleme_kullanilir():
    assert extract_body({"mimeType": "text/plain", "body": {}}, snippet="önizleme") == "önizleme"


def test_state_belirteci_baska_amacla_kullanilamaz():
    assert decode_state_token(create_state_token(5)) == 5
    assert decode_state_token("sahte") is None


# --- Akış ---

def test_google_ayarlari_yoksa_baglanti_kapali(auth_client):
    assert auth_client.get("/inbox/connection").json()["gmail_available"] is False
    assert auth_client.get("/inbox/gmail/connect").status_code == 503


def test_izin_adresi_dogru_kurulur(auth_client, google):
    auth_url = auth_client.get("/inbox/gmail/connect").json()["auth_url"]
    params = parse_qs(urlparse(auth_url).query)

    assert params["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert params["access_type"] == ["offline"]
    assert params["client_id"] == ["istemci"]
    assert decode_state_token(params["state"][0]) is not None


def test_baglama_akisi_anahtari_sifreli_saklar(auth_client, google):
    response = bagla(auth_client)

    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/?gmail=baglandi")
    durum = auth_client.get("/inbox/connection").json()
    assert durum["connected"] is True
    assert durum["email_address"] == "ali@gmail.com"

    from app import models  # veritabanında düz metin anahtar olmamalı
    from app.database import get_db

    db = next(app.dependency_overrides[get_db]())
    kayit = db.query(models.MailConnection).one()
    assert "yenileme-1" not in kayit.encrypted_refresh_token


def test_sahte_state_reddedilir(auth_client, google):
    response = auth_client.get(
        "/inbox/gmail/callback",
        params={"code": "gecerli-kod", "state": "sahte"},
        follow_redirects=False,
    )

    assert response.headers["location"].endswith("/?gmail=hata")
    assert auth_client.get("/inbox/connection").json()["connected"] is False


def test_kullanici_izni_reddederse_iptal_doner(auth_client, google):
    response = auth_client.get(
        "/inbox/gmail/callback", params={"error": "access_denied"}, follow_redirects=False
    )

    assert response.headers["location"].endswith("/?gmail=iptal")


def test_tarama_gmailden_ceker_ve_bilinenleri_yeniden_indirmez(auth_client, google):
    app.dependency_overrides[get_llm_client] = SahteLLM
    bagla(auth_client)

    ilk = auth_client.post("/inbox/sync").json()
    assert ilk["scanned"] == 2
    assert ilk["new"] == 1  # mağaza bülteni ön elemede ayıklandı
    assert sorted(google.indirilen_iletiler()) == ["g1", "g2"]

    google.istekler.clear()
    auth_client.post("/inbox/sync")
    # Kaydedilen g1 yeniden indirilmez; kaydedilmeyen bülten tekrar kontrol edilir.
    assert google.indirilen_iletiler() == ["g2"]
    assert auth_client.get("/inbox/connection").json()["last_synced_at"] is not None


def test_izin_geri_alinmissa_409(auth_client, google):
    bagla(auth_client)
    google.izin_gecersiz = True

    response = auth_client.post("/inbox/sync")

    assert response.status_code == 409


def test_baglanti_kaldirilinca_izin_google_da_da_geri_alinir(auth_client, google):
    app.dependency_overrides[get_llm_client] = SahteLLM
    bagla(auth_client)
    auth_client.post("/inbox/sync")

    response = auth_client.delete("/inbox/connection", params={"delete_emails": "true"})

    assert response.status_code == 204
    assert google.iptal_edilen == ["yenileme-1"]
    assert auth_client.get("/inbox/connection").json()["connected"] is False
    assert auth_client.get("/inbox").json() == []
