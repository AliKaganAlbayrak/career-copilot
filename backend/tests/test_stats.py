"""Huni ve haftalık sayım hesapları ile istatistik uç noktaları."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.stats import funnel, week_start, weekly_counts


def bos_durumlar(**degerler: int) -> dict[str, int]:
    durumlar = {"basvuruldu": 0, "mulakat": 0, "teklif": 0, "red": 0, "kabul": 0}
    durumlar.update(degerler)
    return durumlar


def test_huni_asamalari_kumulatif_sayar():
    adimlar = {a.key: a for a in funnel(bos_durumlar(basvuruldu=5, red=2, mulakat=2, teklif=1))}

    assert adimlar["basvuru"].count == 10
    assert adimlar["donus"].count == 5  # red + mulakat + teklif
    assert adimlar["mulakat"].count == 3  # mulakat + teklif
    assert adimlar["teklif"].count == 1
    assert adimlar["kabul"].count == 0
    assert adimlar["mulakat"].rate == 30.0


def test_bos_huni_sifira_bolmez():
    adimlar = funnel(bos_durumlar())

    assert all(a.count == 0 and a.rate == 0.0 for a in adimlar)


def test_hafta_pazartesi_baslar():
    assert week_start(date(2026, 11, 19)) == date(2026, 11, 16)  # perşembe -> pazartesi
    assert week_start(date(2026, 11, 16)) == date(2026, 11, 16)


def test_haftalik_sayim_bos_haftalari_da_listeler():
    bugun = date(2026, 11, 19)
    anlar = [
        datetime(2026, 11, 18, 10, tzinfo=timezone.utc),
        datetime(2026, 11, 3, 9, tzinfo=timezone.utc),
        datetime(2026, 11, 4, 9),  # dilimsiz: UTC kabul edilir
        datetime(2026, 1, 1, 9, tzinfo=timezone.utc),  # pencere dışı
    ]

    sonuc = weekly_counts(anlar, weeks=4, today=bugun)

    assert [h.week_start for h in sonuc] == [
        date(2026, 10, 26),
        date(2026, 11, 2),
        date(2026, 11, 9),
        date(2026, 11, 16),
    ]
    assert [h.count for h in sonuc] == [0, 2, 0, 1]


def test_stats_huniyi_icerir(auth_client):
    auth_client.post("/applications", json={"company": "A", "position": "X", "status": "mulakat"})
    auth_client.post("/applications", json={"company": "B", "position": "X", "status": "red"})

    body = auth_client.get("/stats").json()

    adimlar = {a["key"]: a["count"] for a in body["funnel"]}
    assert adimlar == {"basvuru": 2, "donus": 2, "mulakat": 1, "teklif": 0, "kabul": 0}


def test_timeline_uc_noktasi(auth_client):
    simdi = datetime.now(timezone.utc)
    for gun_once in (0, 7, 7, 100):
        auth_client.post(
            "/applications",
            json={
                "company": "A",
                "position": "X",
                "applied_at": (simdi - timedelta(days=gun_once)).isoformat(),
            },
        )

    haftalar = auth_client.get("/stats/timeline", params={"weeks": 4}).json()

    assert len(haftalar) == 4
    assert [h["count"] for h in haftalar][-2:] == [2, 1]
    assert sum(h["count"] for h in haftalar) == 3  # 100 gün önceki pencere dışında


def test_timeline_hafta_siniri_dogrulanir(auth_client):
    assert auth_client.get("/stats/timeline", params={"weeks": 0}).status_code == 422
    assert auth_client.get("/stats/timeline", params={"weeks": 53}).status_code == 422
