"""Career Copilot API — FastAPI uygulaması ve uç noktaları."""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db

# Geliştirme kolaylığı için tabloları açılışta oluşturuyoruz.
# Üretimde bunun yerine Alembic ile göç (migration) kullanılacak.
Base.metadata.create_all(bind=engine)

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


def get_application_or_404(application_id: int, db: Session) -> models.Application:
    """Kaydı getirir, yoksa 404 fırlatır. Üç uç nokta bunu paylaşıyor."""
    application = db.get(models.Application, application_id)
    if application is None:
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
) -> models.Application:
    """Yeni başvuru oluşturur."""
    data = payload.model_dump(exclude_none=True)
    data["status"] = payload.status.value
    application = models.Application(**data)

    db.add(application)
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
) -> list[models.Application]:
    """Başvuruları en yeniden eskiye listeler; isteğe bağlı durum filtresi alır."""
    stmt = select(models.Application)
    if status_filter is not None:
        stmt = stmt.where(models.Application.status == status_filter.value)

    stmt = stmt.order_by(models.Application.applied_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@app.get(
    "/applications/{application_id}",
    response_model=schemas.Application,
    tags=["başvurular"],
)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
) -> models.Application:
    """Tek bir başvuruyu getirir."""
    return get_application_or_404(application_id, db)


@app.put(
    "/applications/{application_id}",
    response_model=schemas.Application,
    tags=["başvurular"],
)
def update_application(
    application_id: int,
    payload: schemas.ApplicationUpdate,
    db: Session = Depends(get_db),
) -> models.Application:
    """Kısmi güncelleme: yalnızca gövdede gönderilen alanlar değişir."""
    application = get_application_or_404(application_id, db)

    # exclude_unset: istemcinin hiç göndermediği alanları atla.
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value

    for field, value in changes.items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)
    return application


@app.delete(
    "/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["başvurular"],
)
def delete_application(application_id: int, db: Session = Depends(get_db)) -> Response:
    """Başvuruyu siler."""
    application = get_application_or_404(application_id, db)
    db.delete(application)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/stats", response_model=schemas.Stats, tags=["istatistik"])
def stats(db: Session = Depends(get_db)) -> schemas.Stats:
    """Toplam başvuru sayısı ve durum kırılımı."""
    total = db.scalar(select(func.count()).select_from(models.Application)) or 0

    rows = db.execute(
        select(models.Application.status, func.count())
        .group_by(models.Application.status)
    ).all()

    # Hiç kaydı olmayan durumlar da 0 olarak görünsün ki grafik boşluk yapmasın.
    by_status = {s.value: 0 for s in models.ApplicationStatus}
    for status_value, count in rows:
        by_status[status_value] = count

    return schemas.Stats(total=total, by_status=by_status)
