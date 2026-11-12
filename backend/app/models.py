"""Veritabanı tabloları (SQLAlchemy ORM modelleri)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ApplicationStatus(str, Enum):
    """Bir başvurunun geçebileceği durumlar.

    str'den türediği için hem Python tarafında enum gibi davranır
    hem de JSON'a düz metin olarak serileşir.
    """

    BASVURULDU = "basvuruldu"
    MULAKAT = "mulakat"
    TEKLIF = "teklif"
    RED = "red"
    KABUL = "kabul"


def utcnow() -> datetime:
    """Zaman damgalarını daima UTC üretir (yerel saat sürprizlerini önler)."""
    return datetime.now(timezone.utc)


class User(Base):
    """Kayıtlı kullanıcı. Parolanın kendisi değil, yalnızca özeti saklanır."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email}>"


class Application(Base):
    """Tek bir iş başvurusu kaydı."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Her başvuru bir kullanıcıya aittir; sorgular bu alana göre süzülür.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company: Mapped[str] = mapped_column(String(200), index=True)
    position: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(20),
        default=ApplicationStatus.BASVURULDU.value,
        index=True,
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        index=True,
    )

    def __repr__(self) -> str:  # hata ayıklarken okunabilir çıktı
        return f"<Application {self.id} {self.company} / {self.position} ({self.status})>"
