"""Kimlik doğrulama ve kullanıcılar arası veri izolasyonu testleri."""

from __future__ import annotations

from tests.conftest import kayit_ve_giris

KULLANICI = {"email": "ali@example.com", "password": "gizli-parola-1"}


def test_kayit_basarili_ve_parola_donmez(client):
    response = client.post("/auth/register", json=KULLANICI)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ali@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


def test_ayni_eposta_ikinci_kez_kaydedilemez(client):
    client.post("/auth/register", json=KULLANICI)

    assert client.post("/auth/register", json=KULLANICI).status_code == 409


def test_kisa_parola_reddedilir(client):
    response = client.post("/auth/register", json={"email": "a@example.com", "password": "kisa"})

    assert response.status_code == 422


def test_giris_belirtec_dondurur(client):
    client.post("/auth/register", json=KULLANICI)

    response = client.post(
        "/auth/login",
        data={"username": KULLANICI["email"], "password": KULLANICI["password"]},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_yanlis_parola_401_doner(client):
    client.post("/auth/register", json=KULLANICI)

    response = client.post(
        "/auth/login",
        data={"username": KULLANICI["email"], "password": "yanlis-parola"},
    )

    assert response.status_code == 401


def test_me_oturum_sahibini_dondurur(auth_client):
    response = auth_client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "ali@example.com"


def test_belirtec_olmadan_korunan_uc_nokta_401_doner(client):
    assert client.get("/applications").status_code == 401
    assert client.get("/stats").status_code == 401


def test_gecersiz_belirtec_401_doner(client):
    response = client.get("/applications", headers={"Authorization": "Bearer sacma-belirtec"})

    assert response.status_code == 401


def test_kullanici_baskasinin_basvurusunu_goremez(client):
    ali = kayit_ve_giris(client, "ali@example.com")
    veli = kayit_ve_giris(client, "veli@example.com")
    basvuru = client.post(
        "/applications",
        json={"company": "Aselsan", "position": "Backend Developer"},
        headers=ali,
    ).json()

    assert client.get("/applications", headers=veli).json() == []
    assert client.get(f"/applications/{basvuru['id']}", headers=veli).status_code == 404
    assert client.delete(f"/applications/{basvuru['id']}", headers=veli).status_code == 404
    # Sahibi için kayıt hâlâ yerinde.
    assert client.get(f"/applications/{basvuru['id']}", headers=ali).status_code == 200
