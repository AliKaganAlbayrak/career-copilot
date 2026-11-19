"""Veritabanı tabloları (SQLAlchemy ORM modelleri)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
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
    # Yapay zekâ analizlerinde kullanılan özgeçmiş metni (isteğe bağlı).
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class MailCategory(str, Enum):
    """İşle ilgili bir e-postanın türü."""

    MULAKAT_DAVETI = "mulakat_daveti"
    RED = "red"
    TEKLIF = "teklif"
    BILGI = "bilgi"  # başvuru alındı, test linki, genel bilgilendirme


class SuggestionState(str, Enum):
    """E-postadan çıkan durum önerisinin akıbeti."""

    YOK = "yok"  # bu e-posta bir durum değişikliği önermiyor
    BEKLIYOR = "bekliyor"
    KABUL = "kabul"
    YOKSAYILDI = "yoksayildi"


class EmailMessage(Base):
    """Kullanıcının posta kutusundan gelen, işle ilgili bir e-posta.

    Gizlilik gereği e-postanın gövdesi saklanmaz: yalnızca gönderen, konu,
    tarih ve modelin çıkardığı kısa özet tutulur. İşle ilgisiz e-postalar
    hiç kaydedilmez.
    """

    __tablename__ = "emails"
    # Aynı e-posta ikinci taramada tekrar kaydedilmesin.
    __table_args__ = (UniqueConstraint("owner_id", "provider_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[str] = mapped_column(String(200))  # sağlayıcıdaki ileti kimliği
    sender: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    category: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Eşleşen başvuru; başvuru silinirse bağlantı kopar ama e-posta kalır.
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    suggested_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    suggestion_state: Mapped[str] = mapped_column(String(20), default=SuggestionState.YOK.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<EmailMessage {self.id} {self.sender!r} {self.category}>"

