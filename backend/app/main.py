"""Career Copilot API — FastAPI uygulaması ve uç noktaları."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from . import history, models, schemas, stats as stats_calc
from .ai import router as ai_router
from .auth import get_current_user, router as auth_router
from .inbox import router as inbox_router
from .database import get_db

app = FastAPI(
    title="Career Copilot API",
    description="İş başvurularını takip eden, yapay zekâ destekli platformun API'si.",
    version="0.1.0",
)

# Frontend farklı porttan (Vite: 5173) geldiği için tarayıcı CORS ister.
# Yıldız yerine açık liste kullanıyoruz: kimlik bilgisi taşıyan istekleri
# tarayıcılar yıldızla kabul etmez, ayrıca açık liste daha güvenlidir.
default_origins = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(inbox_router)


def get_application_or_404(application_id: int, db: Session, owner: models.User) -> models.Application:
    """Kaydı getirir; yoksa ya da başkasına aitse 404 fırlatır.

    Başkasının kaydı için 403 yerine 404 dönüyoruz: böylece o numarada
    bir kayıt olup olmadığı bilgisi bile sızmaz.
    """
    application = db.get(models.Application, application_id)
    if application is None or application.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{application_id} numaralı başvuru bulunamadı.",
        )
    return application


@app.get("/health", tags=["sistem"])
def health() -> dict[str, str]:
    """Servisin ayakta olduğunu söyleyen basit uç nokta (CI ve dağıtım için)."""
    return {"status": "ok", "version": app.version}


@app.post(
    "/applications",
    response_model=schemas.Application,
    status_code=status.HTTP_201_CREATED,
    tags=["başvurular"],
)
def create_application(
    payload: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Application:
    """Oturum açmış kullanıcı adına yeni başvuru oluşturur."""
    data = payload.model_dump(exclude_none=True, exclude={"status"})
    application = models.Application(**data, owner_id=current_user.id)

    db.add(application)
    history.record(db, application, payload.status.value, models.ChangeSource.OLUSTURMA)
    db.commit()
    db.refresh(application)  # id ve applied_at veritabanından geri okunur
    return application


@app.get(
    "/applications",
    response_model=list[schemas.Application],
    tags=["başvurular"],
)
def list_applications(
    status_filter: models.ApplicationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[models.Application]:
    """Kullanıcının kendi başvurularını en yeniden eskiye listeler."""
    stmt = select(models.Application).where(models.Application.owner_id == current_user.id)
    if status_filter is not None:
        stmt = stmt.where(models.Application.status == status_filter.value)

    stmt = stmt.order_by(models.Application.applied_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@app.get(
    "/applications/stale",
    response_model=list[schemas.StaleApplication],
    tags=["başvurular"],
)
def stale_applications(
    days: int = Query(default=14, ge=1, le=180),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[schemas.StaleApplication]:
    """Sonucu beklenen ama `days` gündür durumu değişmemiş başvurular.

    "Haber var mı?" hatırlatması için. Bu rota /applications/{application_id}'den
    önce tanımlı olmalı; yoksa FastAPI "stale" sözcüğünü id sanıp 422 döndürür.
    """
    last_change = (
        select(
            models.StatusChange.application_id,
            func.max(models.StatusChange.changed_at).label("last_change_at"),
        )
        .group_by(models.StatusChange.application_id)
        .subquery()
    )
    rows = db.execute(
        select(models.Application, last_change.c.last_change_at)
        .join(last_change, last_change.c.application_id == models.Application.id)
        .where(
            models.Application.owner_id == current_user.id,
            # Sonuçlanmış başvurular için beklenecek haber yok.
            models.Application.status.in_(
                [models.ApplicationStatus.BASVURULDU.value, models.ApplicationStatus.MULAKAT.value]
            ),
        )
    ).all()

    now = datetime.now(timezone.utc)
    result = []
    for application, last_change_at in rows:
        if last_change_at.tzinfo is None:  # SQLite saat dilimi saklamaz; UTC'dir
            last_change_at = last_change_at.replace(tzinfo=timezone.utc)
        quiet = (now - last_change_at).days
        if quiet >= days:
            result.append(
                schemas.StaleApplication(
                    id=application.id,
                    company=application.company,
                    position=application.position,
                    status=application.status,
                    last_change_at=last_change_at,
                    days_quiet=quiet,
                )
            )
    return sorted(result, key=lambda r: r.days_quiet, reverse=True)


@app.get(
    "/applications/{application_id}/history",
    response_model=list[schemas.StatusChange],
    tags=["başvurular"],
)
def application_history(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[models.StatusChange]:
    """Başvurunun durum geçmişi, eskiden yeniye."""
    application = get_application_or_404(application_id, db, current_user)
    return list(
        db.scalars(
            select(models.StatusChange)
            .where(models.StatusChange.application_id == application.id)
            .order_by(models.StatusChange.changed_at, models.StatusChange.id)
        )
    )


@app.get(
    "/applications/{application_id}",
    response_model=schemas.Application,
    tags=["başvurular"],
)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Application:
    """Tek bir başvuruyu getirir."""
    return get_application_or_404(application_id, db, current_user)


@app.put(
    "/applications/{application_id}",
    response_model=schemas.Application,
    tags=["başvurular"],
)
def update_application(
    application_id: int,
    payload: schemas.ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Application:
    """Kısmi güncelleme: yalnızca gövdede gönderilen alanlar değişir."""
    application = get_application_or_404(application_id, db, current_user)

    # exclude_unset: istemcinin hiç göndermediği alanları atla.
    changes = payload.model_dump(exclude_unset=True)
    new_status = changes.pop("status", None)

    for field, value in changes.items():
        setattr(application, field, value)
    if new_status is not None:
        history.record(db, application, new_status.value, models.ChangeSource.MANUEL)

    db.commit()
    db.refresh(application)
    return application


@app.delete(
    "/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["başvurular"],
)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> Response:
    """Başvuruyu siler."""
    application = get_application_or_404(application_id, db, current_user)
    # Bağlı e-postalar kalır, yalnızca bağlantı kopar. Veritabanındaki
    # ON DELETE SET NULL da bunu yapar, ama SQLite foreign key'leri varsayılan
    # olarak uygulamadığı için burada açıkça yapıyoruz.
    db.execute(
        update(models.EmailMessage)
        .where(models.EmailMessage.application_id == application.id)
        .values(application_id=None)
    )
    # Geçmiş başvuruyla birlikte gider (ON DELETE CASCADE'in SQLite'taki karşılığı).
    db.execute(
        delete(models.StatusChange).where(models.StatusChange.application_id == application.id)
    )
    db.delete(application)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/stats", response_model=schemas.Stats, tags=["istatistik"])
def stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Stats:
    """Kullanıcının toplam başvuru sayısı ve durum kırılımı."""
    rows = db.execute(
        select(models.Application.status, func.count())
        .where(models.Application.owner_id == current_user.id)
        .group_by(models.Application.status)
    ).all()

    # Hiç kaydı olmayan durumlar da 0 olarak görünsün ki grafik boşluk yapmasın.
    by_status = {s.value: 0 for s in models.ApplicationStatus}
    for status_value, count in rows:
        by_status[status_value] = count

    # Her başvurunun geçmişte bulunduğu durumlar (şu anki dahil).
    reached: dict[int, set[str]] = {}
    for app_id, held_status in db.execute(
        select(models.StatusChange.application_id, models.StatusChange.to_status)
        .join(models.Application, models.Application.id == models.StatusChange.application_id)
        .where(models.Application.owner_id == current_user.id)
    ):
        reached.setdefault(app_id, set()).add(held_status)

    return schemas.Stats(
        total=sum(by_status.values()),
        by_status=by_status,
        funnel=stats_calc.funnel(list(reached.values())),
    )


@app.get("/stats/timeline", response_model=list[schemas.WeekCount], tags=["istatistik"])
def stats_timeline(
    weeks: int = Query(default=12, ge=1, le=52),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[schemas.WeekCount]:
    """Son N haftanın haftalık başvuru sayıları (eskiden yeniye)."""
    # Kişisel bir başvuru listesi küçüktür; tarihleri çekip Python'da gruplamak
    # SQLite ile PostgreSQL arasında tarih fonksiyonu farkıyla uğraşmaktan iyidir.
    moments = db.scalars(
        select(models.Application.applied_at).where(
            models.Application.owner_id == current_user.id
        )
    )
    today = datetime.now(timezone.utc).date()
    return stats_calc.weekly_counts(moments, weeks, today)
