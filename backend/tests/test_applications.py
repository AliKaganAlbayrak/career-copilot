"""Başvuru uç noktalarının davranış testleri."""

from __future__ import annotations


def ornek_basvuru(**kwargs) -> dict:
    payload = {
        "company": "Aselsan",
        "position": "Backend Developer",
        "status": "basvuruldu",
        "location": "Ankara",
        "link": "https://example.com/ilan/1",
        "notes": "Referans: kariyer fuarı",
    }
    payload.update(kwargs)
    return payload


def test_basvuru_olusturulur(client):
    response = client.post("/applications", json=ornek_basvuru())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["company"] == "Aselsan"
    assert body["status"] == "basvuruldu"
    assert body["applied_at"]  # sunucu otomatik doldurdu


def test_liste_en_yeniden_eskiye_gelir(client):
    client.post("/applications", json=ornek_basvuru(company="A", applied_at="2026-01-01T09:00:00Z"))
    client.post("/applications", json=ornek_basvuru(company="B", applied_at="2026-05-01T09:00:00Z"))

    sirketler = [item["company"] for item in client.get("/applications").json()]

    assert sirketler == ["B", "A"]


def test_duruma_gore_filtrelenir(client):
    client.post("/applications", json=ornek_basvuru(company="A", status="basvuruldu"))
    client.post("/applications", json=ornek_basvuru(company="B", status="mulakat"))

    sonuc = client.get("/applications", params={"status": "mulakat"}).json()

    assert len(sonuc) == 1
    assert sonuc[0]["company"] == "B"


def test_olmayan_kayit_404_doner(client):
    assert client.get("/applications/9999").status_code == 404


def test_kismi_guncelleme_diger_alanlari_bozmaz(client):
    olusan = client.post("/applications", json=ornek_basvuru()).json()

    guncel = client.put(
        f"/applications/{olusan['id']}",
        json={"status": "mulakat"},
    ).json()

    assert guncel["status"] == "mulakat"
    assert guncel["company"] == olusan["company"]
    assert guncel["location"] == olusan["location"]


def test_silme_204_doner_ve_kayit_gider(client):
    olusan = client.post("/applications", json=ornek_basvuru()).json()

    assert client.delete(f"/applications/{olusan['id']}").status_code == 204
    assert client.get(f"/applications/{olusan['id']}").status_code == 404


def test_istatistikler_durum_kirilimi_verir(client):
    client.post("/applications", json=ornek_basvuru(status="basvuruldu"))
    client.post("/applications", json=ornek_basvuru(status="mulakat"))
    client.post("/applications", json=ornek_basvuru(status="mulakat"))

    stats = client.get("/stats").json()

    assert stats["total"] == 3
    assert stats["by_status"]["mulakat"] == 2
    assert stats["by_status"]["kabul"] == 0


def test_gecersiz_durum_reddedilir(client):
    response = client.post("/applications", json=ornek_basvuru(status="bilinmeyen"))

    assert response.status_code == 422
