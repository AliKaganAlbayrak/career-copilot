"""Durum geçmişini yazan tek yer.

Durumu değiştiren her kod yolu (oluşturma, tablodan değiştirme, e-posta
önerisini kabul) buradan geçer; böylece geçmiş hiçbir yolda atlanmaz.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import models


def record(
    db: Session,
    application: models.Application,
    new_status: str,
    source: models.ChangeSource,
) -> None:
    """Başvurunun durumunu değiştirir ve geçmişe yazar. Commit çağırana kalır.

    Durum zaten aynıysa hiçbir şey yapmaz: geçmişte anlamsız tekrarlar olmasın.
    """
    old = application.status if application.id is not None else None
    if old == new_status:
        return
    application.status = new_status
    if application.id is None:
        db.flush()  # yeni başvurunun id'si geçmiş kaydı için gerekli
    change = models.StatusChange(
        application_id=application.id,
        from_status=old,
        to_status=new_status,
        source=source.value,
    )
    if source is models.ChangeSource.OLUSTURMA:
        # İlk kayıt başvuru tarihinde olmuş sayılır (geçmiş tarihli başvurular için).
        change.changed_at = application.applied_at
    db.add(change)
