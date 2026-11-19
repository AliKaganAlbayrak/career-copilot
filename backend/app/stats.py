"""İstatistik hesapları: süreç hunisi ve haftalık başvuru sayıları.

Burada veritabanı ya da HTTP yok; yalnızca sayılar girer, sayılar çıkar.
Böylece hesap mantığı uç noktalardan bağımsız, tek başına test edilir.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

from .models import ApplicationStatus as S
from .schemas import FunnelStep, WeekCount

# Huni aşamaları: her aşama, en az o noktaya ulaşmış başvuruları sayar.
# Sınır: kayıtta yalnızca *şu anki* durum tutuluyor. Mülakattan sonra reddedilen
# bir başvuru "red" olduğu için mülakat aşamasında görünmez. Tam doğruluk için
# durum geçmişi tablosu gerekir (yol haritasında).
FUNNEL: list[tuple[str, str, set[str]]] = [
    ("basvuru", "Başvuru", {s.value for s in S}),
    ("donus", "Geri dönüş", {S.MULAKAT.value, S.TEKLIF.value, S.KABUL.value, S.RED.value}),
    ("mulakat", "Mülakat", {S.MULAKAT.value, S.TEKLIF.value, S.KABUL.value}),
    ("teklif", "Teklif", {S.TEKLIF.value, S.KABUL.value}),
    ("kabul", "Kabul", {S.KABUL.value}),
]


def funnel(by_status: dict[str, int]) -> list[FunnelStep]:
    """Durum kırılımından huni aşamalarını ve ilk aşamaya göre oranları üretir."""
    total = sum(by_status.values())
    steps = []
    for key, label, statuses in FUNNEL:
        count = sum(by_status.get(s, 0) for s in statuses)
        rate = round(count / total * 100, 1) if total else 0.0
        steps.append(FunnelStep(key=key, label=label, count=count, rate=rate))
    return steps


def week_start(day: date) -> date:
    """Günün içinde bulunduğu haftanın pazartesisi (ISO hafta başı)."""
    return day - timedelta(days=day.weekday())


def _as_utc_date(moment: datetime) -> date:
    # SQLite saat dilimini saklamaz; dilimsiz gelen değeri UTC kabul ediyoruz
    # çünkü uygulama zaman damgalarını daima UTC üretiyor.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).date()


def weekly_counts(moments: Iterable[datetime], weeks: int, today: date) -> list[WeekCount]:
    """Son `weeks` haftanın her biri için başvuru sayısı, eskiden yeniye.

    Hiç başvuru olmayan haftalar da 0 olarak listede yer alır; yoksa grafikte
    boşluklar kaybolur ve sessiz haftalar görünmez olur.
    """
    current = week_start(today)
    starts = [current - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    counts = dict.fromkeys(starts, 0)

    for moment in moments:
        start = week_start(_as_utc_date(moment))
        if start in counts:
            counts[start] += 1

    return [WeekCount(week_start=start, count=counts[start]) for start in starts]
