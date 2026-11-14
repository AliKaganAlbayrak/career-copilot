"""Pydantic şemaları: API'ye giren ve çıkan verinin sözleşmesi.

ORM modelleri veritabanının şeklini, bu şemalar API'nin şeklini tanımlar.
İkisini ayrı tutmak, veritabanını değiştirdiğinde API'yi kırmamanı sağlar.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import ApplicationStatus


class ApplicationBase(BaseModel):
    """Oluşturma ve okuma şemalarının paylaştığı alanlar."""

    company: str = Field(min_length=1, max_length=200)
    position: str = Field(min_length=1, max_length=200)
    status: ApplicationStatus = ApplicationStatus.BASVURULDU
    location: str | None = Field(default=None, max_length=200)
    link: str | None = None
    notes: str | None = None


class ApplicationCreate(ApplicationBase):
    """POST /applications gövdesi. applied_at verilmezse sunucu şimdiyi yazar."""

    applied_at: datetime | None = None


class ApplicationUpdate(BaseModel):
    """PUT /applications/{id} gövdesi.

    Tüm alanlar isteğe bağlı: yalnızca gönderdiğin alanlar güncellenir
    (kısmi güncelleme). Gönderilmeyen alan eskisi gibi kalır.
    """

    company: str | None = Field(default=None, min_length=1, max_length=200)
    position: str | None = Field(default=None, min_length=1, max_length=200)
    status: ApplicationStatus | None = None
    location: str | None = Field(default=None, max_length=200)
    link: str | None = None
    notes: str | None = None
    applied_at: datetime | None = None


class Application(ApplicationBase):
    """API'nin döndürdüğü başvuru kaydı."""

    # from_attributes: ORM nesnesini doğrudan bu şemaya çevirebilmek için.
    model_config = ConfigDict(from_attributes=True)

    id: int
    applied_at: datetime


class Stats(BaseModel):
    """GET /stats çıktısı."""

    total: int
    by_status: dict[str, int]


class UserCreate(BaseModel):
    """POST /auth/register gövdesi."""

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)


class User(BaseModel):
    """API'nin döndürdüğü kullanıcı. Parola özeti bilerek burada yok."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    """Başarılı girişte dönen erişim belirteci."""

    access_token: str
    token_type: str = "bearer"


class CvIn(BaseModel):
    """PUT /ai/cv gövdesi: özgeçmişin düz metin hâli."""

    cv_text: str = Field(min_length=1, max_length=30_000)


class CvOut(BaseModel):
    """Kayıtlı özgeçmiş; henüz kaydedilmediyse null."""

    cv_text: str | None


class AnalyzeRequest(BaseModel):
    """POST /ai/analyze gövdesi. cv_text verilmezse kayıtlı özgeçmiş kullanılır."""

    job_description: str = Field(min_length=30, max_length=20_000)
    cv_text: str | None = Field(default=None, max_length=30_000)


class AnalysisResult(BaseModel):
    """İlan ile özgeçmişin eşleşme analizi."""

    match_score: int = Field(ge=0, le=100)
    strengths: list[str]
    gaps: list[str]
    summary: str


class CoverLetterRequest(BaseModel):
    """POST /ai/cover-letter gövdesi."""

    job_description: str = Field(min_length=30, max_length=20_000)
    company: str = Field(min_length=1, max_length=200)
    position: str = Field(min_length=1, max_length=200)
    cv_text: str | None = Field(default=None, max_length=30_000)
    language: Literal["tr", "en"] = "tr"


class CoverLetter(BaseModel):
    """Üretilen ön yazı."""

    cover_letter: str
