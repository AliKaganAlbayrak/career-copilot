"""Yapay zekâ uç noktaları: CV saklama, ilan analizi, ön yazı üretimi."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models, prompts, schemas
from .auth import get_current_user
from .database import get_db
from .llm import LLMClient, LLMError, get_llm_client

router = APIRouter(prefix="/ai", tags=["yapay zekâ"])


def resolve_cv(cv_text: str | None, user: models.User) -> str:
    """İstekte gelen özgeçmişi, yoksa kayıtlı olanı döndürür; ikisi de yoksa 400."""
    cv = (cv_text or user.cv_text or "").strip()
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Önce özgeçmişini kaydet ya da istekte cv_text gönder.",
        )
    return cv


def ask_model(llm: LLMClient, prompt: str, *, system: str, json_mode: bool = False) -> str:
    """Modeli çağırır; ulaşılamazsa anlaşılır bir 503 döndürür."""
    try:
        return llm.generate(prompt, system=system, json_mode=json_mode)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yapay zekâ servisine ulaşılamadı. Ollama çalışıyor mu?",
        ) from exc


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


@router.post("/analyze", response_model=schemas.AnalysisResult)
def analyze(
    payload: schemas.AnalyzeRequest,
    current_user: models.User = Depends(get_current_user),
    llm: LLMClient = Depends(get_llm_client),
) -> schemas.AnalysisResult:
    """İlan ile özgeçmişi karşılaştırır: eşleşme puanı, güçlü yönler, eksikler."""
    cv = resolve_cv(payload.cv_text, current_user)
    raw = ask_model(
        llm,
        prompts.build_analysis_prompt(payload.job_description, cv),
        system=prompts.ANALYSIS_SYSTEM,
        json_mode=True,
    )
    try:
        return prompts.parse_analysis(raw)
    except ValueError as exc:
        # 502: bizim sunucu sağlam, hata arkadaki servisin (modelin) yanıtında.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Model yanıtı okunamadı: {exc}",
        ) from exc


@router.post("/cover-letter", response_model=schemas.CoverLetter)
def cover_letter(
    payload: schemas.CoverLetterRequest,
    current_user: models.User = Depends(get_current_user),
    llm: LLMClient = Depends(get_llm_client),
) -> schemas.CoverLetter:
    """İlana ve özgeçmişe göre kişiye özel ön yazı üretir."""
    cv = resolve_cv(payload.cv_text, current_user)
    text = ask_model(
        llm,
        prompts.build_cover_letter_prompt(
            payload.job_description,
            cv,
            payload.company,
            payload.position,
            payload.language,
        ),
        system=prompts.COVER_LETTER_SYSTEM,
    ).strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Model boş yanıt döndürdü.",
        )
    return schemas.CoverLetter(cover_letter=text)
