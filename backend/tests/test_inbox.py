"""Posta kutusu: ön eleme, sınıflandırma, eşleştirme ve öneri akışı.
Gerçek posta kutusu ve model yerine sahteleri kullanılır."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.inbox import mail_provider_or_503
from app.llm import get_llm_client
from app.mail import DemoMailProvider, MailMessage
from app.mail_classifier import Classification, looks_job_related, match_company, parse_classification
from app.main import app
from tests.conftest import kayit_ve_giris

# Konudaki sözcüğe göre sınıflandırma yanıtı: gerçek modelin yerine geçer.
CEVAPLAR = {
    "mülakat": {"is_job_related": True, "category": "mulakat_daveti", "company": "Aselsan",
                "summary": "25 Kasım'da teknik mülakata davet ediliyorsun."},
    "hakkında": {"is_job_related": True, "category": "red", "company": "Getir",
                 "summary": "Başvurun olumsuz sonuçlandı."},
    "ulaştı": {"is_job_related": True, "category": "bilgi", "company": "Trendyol",
               "summary": "Başvurun alındı."},
}


class SahteLLM:
    def __init__(self) -> None:
        self.istemler: list[str] = []

    def generate(self, prompt: str, *, system: str, json_mode: bool = False) -> str:
        self.istemler.append(prompt)
        konu = next(line for line in prompt.splitlines() if line.startswith("Konu:"))
        for anahtar, cevap in CEVAPLAR.items():
            if anahtar in konu:
                return json.dumps(cevap)
        return json.dumps({"is_job_related": False, "category": "bilgi", "summary": ""})


@pytest.fixture()
def llm(auth_client):
    sahte = SahteLLM()
    app.dependency_overrides[get_llm_client] = lambda: sahte
    app.dependency_overrides[mail_provider_or_503] = DemoMailProvider
    return sahte


def basvuru(client, company, status="basvuruldu", headers=None):
    return client.post(
        "/applications",
        json={"company": company, "position": "Geliştirici", "status": status},
        headers=headers,
    ).json()


# --- Saf işlevler ---

def test_on_eleme_bulteni_ayiklar():
    bulten = MailMessage("x", "Kahve <b@kahve.example>", "Bu hafta indirim", datetime.now(timezone.utc), "Kahve")
    davet = MailMessage("y", "ik@aselsan.com.tr", "Merhaba", datetime.now(timezone.utc), "Görüşme")

    assert looks_job_related(bulten, ["Aselsan"]) is False
    assert looks_job_related(davet, []) is True  # iş sözcüğü: görüşme


def test_bilinmeyen_tur_bilgi_sayilir():
    sonuc = parse_classification('{"is_job_related": true, "category": "tuhaf", "company": "null"}')

    assert sonuc.category == "bilgi"
    assert sonuc.company is None


def test_bozuk_siniflandirma_reddedilir():
    with pytest.raises(ValueError):
        parse_classification("json değil")


def test_gonderen_alan_adindan_eslesir():
    mesaj = MailMessage("x", "İK <ik@aselsan.com.tr>", "Merhaba", datetime.now(timezone.utc), "")
    bos = Classification(True, "bilgi", None, "")

    assert match_company(bos, mesaj, {7: "Havelsan", 3: "Aselsan"}) == 3
    assert match_company(bos, mesaj, {7: "Havelsan"}) is None


# --- Uç noktalar ---

def test_tarama_ise_ilgili_postalari_kaydeder(auth_client, llm):
    aselsan = basvuru(auth_client, "Aselsan")
    getir = basvuru(auth_client, "Getir")

    sonuc = auth_client.post("/inbox/sync").json()

    assert sonuc == {"scanned": 4, "job_related": 3, "new": 3}
    # Bülten ön elemede ayıklandı, modele hiç gitmedi.
    assert not any("indirim" in istem for istem in llm.istemler)

    postalar = {p["category"]: p for p in auth_client.get("/inbox").json()}
    assert postalar["mulakat_daveti"]["application_id"] == aselsan["id"]
    assert postalar["mulakat_daveti"]["suggested_status"] == "mulakat"
    assert postalar["mulakat_daveti"]["suggestion_state"] == "bekliyor"
    assert postalar["red"]["application_id"] == getir["id"]
    assert postalar["bilgi"]["suggestion_state"] == "yok"  # Trendyol takipte değil


def test_ikinci_tarama_tekrar_kaydetmez(auth_client, llm):
    auth_client.post("/inbox/sync")
    istem_sayisi = len(llm.istemler)

    sonuc = auth_client.post("/inbox/sync").json()

    assert sonuc["new"] == 0
    assert len(auth_client.get("/inbox").json()) == 3
    assert len(llm.istemler) == istem_sayisi  # görülen postalar modele yeniden gitmedi


def test_oneri_kabul_edilince_durum_degisir(auth_client, llm):
    aselsan = basvuru(auth_client, "Aselsan")
    auth_client.post("/inbox/sync")
    davet = next(p for p in auth_client.get("/inbox").json() if p["category"] == "mulakat_daveti")

    response = auth_client.post(f"/inbox/{davet['id']}/accept")

    assert response.status_code == 200
    assert response.json()["suggestion_state"] == "kabul"
    assert auth_client.get(f"/applications/{aselsan['id']}").json()["status"] == "mulakat"
    # İkinci kez kabul edilemez.
    assert auth_client.post(f"/inbox/{davet['id']}/accept").status_code == 400


def test_oneri_yoksayilinca_durum_degismez(auth_client, llm):
    getir = basvuru(auth_client, "Getir")
    auth_client.post("/inbox/sync")
    red = next(p for p in auth_client.get("/inbox").json() if p["category"] == "red")

    assert auth_client.post(f"/inbox/{red['id']}/dismiss").json()["suggestion_state"] == "yoksayildi"
    assert auth_client.get(f"/applications/{getir['id']}").json()["status"] == "basvuruldu"


def test_zaten_o_durumdaysa_oneri_yapilmaz(auth_client, llm):
    basvuru(auth_client, "Aselsan", status="mulakat")
    auth_client.post("/inbox/sync")

    davet = next(p for p in auth_client.get("/inbox").json() if p["category"] == "mulakat_daveti")
    assert davet["suggestion_state"] == "yok"


def test_basvuru_silinince_posta_kalir_baglanti_kopar(auth_client, llm):
    aselsan = basvuru(auth_client, "Aselsan")
    auth_client.post("/inbox/sync")
    auth_client.delete(f"/applications/{aselsan['id']}")

    davet = next(p for p in auth_client.get("/inbox").json() if p["category"] == "mulakat_daveti")
    assert davet["application_id"] is None
    assert auth_client.post(f"/inbox/{davet['id']}/accept").status_code == 409


def test_baskasinin_postasi_gorunmez(client, llm):
    ali = kayit_ve_giris(client, "ali2@example.com")
    veli = kayit_ve_giris(client, "veli@example.com")
    client.post("/inbox/sync", headers=ali)
    posta = client.get("/inbox", headers=ali).json()[0]

    assert client.get("/inbox", headers=veli).json() == []
    assert client.post(f"/inbox/{posta['id']}/dismiss", headers=veli).status_code == 404


def test_saglayici_yoksa_503(auth_client):
    assert auth_client.post("/inbox/sync").status_code == 503
