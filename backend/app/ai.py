"""Yapay zekâ uç noktaları: CV saklama, ilan analizi, ön yazı üretimi."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import get_current_user
from .database import get_db

router = APIRouter(prefix="/ai", tags=["yapay zekâ"])


@router.get("/cv", response_model=schemas.CvOut)
def get_cv(current_user: models.User = Depends(get_current_user)) -> schemas.CvOut:
    """Kullanıcının kayıtlı özgeçmiş metnini döndürür."""
    return schemas.CvOut(cv_text=current_user.cv_text)


@router.put("/cv", response_model=schemas.CvOut)
def save_cv(
    payload: schemas.CvIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.CvOut:
    """Özgeçmişi kaydeder; sonraki analizler bunu kendiliğinden kullanır."""
    current_user.cv_text = payload.cv_text.strip()
    db.commit()
    return schemas.CvOut(cv_text=current_user.cv_text)
