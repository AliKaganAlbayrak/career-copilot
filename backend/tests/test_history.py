"""Durum geçmişi, geçmişe dayalı huni ve "haber var mı" listesi."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.inbox import mail_provider_or_503
from app.llm import get_llm_client
from app.mail import DemoMailProvider
from app.main import app
from app.stats import funnel
from tests.conftest import kayit_ve_giris
from tests.test_inbox import SahteLLM


def ekle(client, company="Aselsan", status="basvuruldu", gun_once=0, headers=None):
    applied = (datetime.now(timezone.utc) - timedelta(days=gun_once)).isoformat()
    return client.post(
        "/applications",
        json={"company": company, "position": "Geliştirici", "status": status, "applied_at": applied},
        headers=headers,
    ).json()


def gecmis(client, app_id):
    return client.get(f"/applications/{app_id}/history").json()


def test_olusturma_ilk_kaydi_basvuru_tarihinde_yazar(auth_client):
    basvuru = ekle(auth_client, gun_once=10)

    kayitlar = gecmis(auth_client, basvuru["id"])

    assert len(kayitlar) == 1
    assert kayitlar[0]["from_status"] is None
    assert kayitlar[0]["to_status"] == "basvuruldu"
    assert kayitlar[0]["source"] == "olusturma"
    assert kayitlar[0]["changed_at"][:10] == basvuru["applied_at"][:10]


def test_durum_degisikligi_kaydedilir_tekrar_ve_diger_alanlar_kaydedilmez(auth_client):
    basvuru = ekle(auth_client)
    auth_client.put(f"/applications/{basvuru['id']}", json={"status": "mulakat"})
    auth_client.put(f"/applications/{basvuru['id']}", json={"status": "mulakat"})  # aynı durum
    auth_client.put(f"/applications/{basvuru['id']}", json={"notes": "Teknik tur iyi geçti"})

    kayitlar = gecmis(auth_client, basvuru["id"])

    assert [(k["from_status"], k["to_status"], k["source"]) for k in kayitlar] == [
        (None, "basvuruldu", "olusturma"),
        ("basvuruldu", "mulakat", "manuel"),
    ]


def test_eposta_onerisi_kaynak_olarak_yazilir(auth_client):
    app.dependency_overrides[get_llm_client] = SahteLLM
    app.dependency_overrides[mail_provider_or_503] = DemoMailProvider
    basvuru = ekle(auth_client, company="Aselsan")
    auth_client.post("/inbox/sync")
    davet = next(p for p in auth_client.get("/inbox").json() if p["category"] == "mulakat_daveti")

    auth_client.post(f"/inbox/{davet['id']}/accept")

    assert gecmis(auth_client, basvuru["id"])[-1]["source"] == "eposta"


def test_mulakat_sonrasi_red_hunide_mulakat_sayilir(auth_client):
    basvuru = ekle(auth_client)
    auth_client.put(f"/applications/{basvuru['id']}", json={"status": "mulakat"})
    auth_client.put(f"/applications/{basvuru['id']}", json={"status": "red"})
    ekle(auth_client, company="Getir")

    adimlar = {a["key"]: a["count"] for a in auth_client.get("/stats").json()["funnel"]}

    assert adimlar == {"basvuru": 2, "donus": 1, "mulakat": 1, "teklif": 0, "kabul": 0}


def test_huni_kumeleri_dogru_sayar():
    adimlar = {a.key: a.count for a in funnel([{"basvuruldu", "mulakat", "red"}, {"basvuruldu"}])}

    assert adimlar["mulakat"] == 1
    assert adimlar["donus"] == 1


def test_haber_var_mi_listesi(auth_client):
    eski = ekle(auth_client, company="Eski", gun_once=20)
    ekle(auth_client, company="Yeni", gun_once=2)
    ekle(auth_client, company="Sonuclanmis", status="red", gun_once=30)
    tazelenen = ekle(auth_client, company="Tazelenen", gun_once=25)
    auth_client.put(f"/applications/{tazelenen['id']}", json={"status": "mulakat"})

    sonuc = auth_client.get("/applications/stale", params={"days": 14})

    assert sonuc.status_code == 200  # "stale" bir id sanılmadı
    assert [(s["id"], s["days_quiet"] >= 20) for s in sonuc.json()] == [(eski["id"], True)]


def test_silinen_basvurunun_gecmisi_de_gider(auth_client):
    basvuru = ekle(auth_client)
    auth_client.delete(f"/applications/{basvuru['id']}")

    from app import models  # doğrudan veritabanına bak
    from app.database import get_db

    db = next(app.dependency_overrides[get_db]())
    assert db.query(models.StatusChange).count() == 0


def test_baskasinin_gecmisi_gorulemez(client):
    ali = kayit_ve_giris(client, "ali@example.com")
    veli = kayit_ve_giris(client, "veli@example.com")
    basvuru = ekle(client, headers=ali)

    assert client.get(f"/applications/{basvuru['id']}/history", headers=veli).status_code == 404
    assert client.get("/applications/stale", headers=veli).json() == []
