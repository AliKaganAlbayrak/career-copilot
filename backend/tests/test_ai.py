"""Yapay zekâ uç noktaları. Gerçek model yerine sahte bir istemci kullanılır:
testler hızlı, tekrarlanabilir ve internetsiz çalışır."""

from __future__ import annotations

import json

import pytest

from app.llm import LLMError, get_llm_client
from app.main import app
from app.prompts import parse_analysis

ILAN = "Python ve FastAPI bilen, SQL deneyimi olan bir backend geliştirici arıyoruz."
CV = "Bilgisayar mühendisliği öğrencisi. Python, FastAPI ve SQLite ile projeler geliştirdi."
GECERLI_ANALIZ = json.dumps(
    {
        "match_score": 82,
        "strengths": ["Python", "FastAPI"],
        "gaps": ["PostgreSQL deneyimi"],
        "summary": "İlanla güçlü biçimde örtüşüyor.",
    }
)


class SahteLLM:
    """LLMClient arayüzünü uygular: hazır bir yanıt döndürür, gelen istemi saklar."""

    def __init__(self, yanit: str = "", hata: bool = False) -> None:
        self.yanit = yanit
        self.hata = hata
        self.son_istem = ""
        self.son_json_mode = False

    def generate(self, prompt: str, *, system: str, json_mode: bool = False) -> str:
        if self.hata:
            raise LLMError("bağlantı yok")
        self.son_istem = prompt
        self.son_json_mode = json_mode
        return self.yanit


@pytest.fixture()
def sahte_llm(auth_client):
    """Uygulamadaki gerçek istemciyi sahtesiyle değiştirir."""
    llm = SahteLLM()
    app.dependency_overrides[get_llm_client] = lambda: llm
    return llm


def test_cv_kaydedilir_ve_geri_okunur(auth_client):
    assert auth_client.get("/ai/cv").json() == {"cv_text": None}

    auth_client.put("/ai/cv", json={"cv_text": CV})

    assert auth_client.get("/ai/cv").json() == {"cv_text": CV}


def test_cv_olmadan_analiz_400_doner(auth_client, sahte_llm):
    response = auth_client.post("/ai/analyze", json={"job_description": ILAN})

    assert response.status_code == 400


def test_analiz_kayitli_cv_ile_calisir(auth_client, sahte_llm):
    auth_client.put("/ai/cv", json={"cv_text": CV})
    sahte_llm.yanit = GECERLI_ANALIZ

    response = auth_client.post("/ai/analyze", json={"job_description": ILAN})

    assert response.status_code == 200
    body = response.json()
    assert body["match_score"] == 82
    assert body["strengths"] == ["Python", "FastAPI"]
    assert body["gaps"] == ["PostgreSQL deneyimi"]
    # Modele hem ilan hem özgeçmiş gitti ve JSON modu istendi.
    assert ILAN in sahte_llm.son_istem
    assert CV in sahte_llm.son_istem
    assert sahte_llm.son_json_mode is True


def test_bozuk_model_yaniti_502_doner(auth_client, sahte_llm):
    sahte_llm.yanit = "bu bir JSON değil"

    response = auth_client.post("/ai/analyze", json={"job_description": ILAN, "cv_text": CV})

    assert response.status_code == 502


def test_modele_ulasilamazsa_503_doner(auth_client, sahte_llm):
    sahte_llm.hata = True

    response = auth_client.post("/ai/analyze", json={"job_description": ILAN, "cv_text": CV})

    assert response.status_code == 503


def test_on_yazi_uretilir(auth_client, sahte_llm):
    sahte_llm.yanit = "  Sayın yetkili, ilanınızı ilgiyle okudum.  "

    response = auth_client.post(
        "/ai/cover-letter",
        json={
            "job_description": ILAN,
            "cv_text": CV,
            "company": "Aselsan",
            "position": "Backend Developer",
        },
    )

    assert response.status_code == 200
    assert response.json()["cover_letter"] == "Sayın yetkili, ilanınızı ilgiyle okudum."
    assert "Aselsan" in sahte_llm.son_istem
    assert "Backend Developer" in sahte_llm.son_istem


def test_ai_uc_noktalari_oturum_ister(client):
    assert client.get("/ai/cv").status_code == 401
    assert client.post("/ai/analyze", json={"job_description": ILAN}).status_code == 401


def test_puan_sinirlarin_disina_tasarsa_kirpilir():
    assert parse_analysis('{"match_score": 150}').match_score == 100
    assert parse_analysis('{"match_score": -5}').match_score == 0


def test_liste_yerine_metin_gelirse_listeye_cevrilir():
    sonuc = parse_analysis('{"match_score": "70", "strengths": "Python", "gaps": null}')

    assert sonuc.match_score == 70
    assert sonuc.strengths == ["Python"]
    assert sonuc.gaps == []


def test_puansiz_yanit_reddedilir():
    with pytest.raises(ValueError):
        parse_analysis('{"summary": "puan yok"}')
