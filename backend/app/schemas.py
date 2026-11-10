"""Pydantic şemaları: API'ye giren ve çıkan verinin sözleşmesi.

ORM modelleri veritabanının şeklini, bu şemalar API'nin şeklini tanımlar.
İkisini ayrı tutmak, veritabanını değiştirdiğinde API'yi kırmamanı sağlar.
"""

from __future__ import annotations

from datetime import datetime

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
