"""Posta sağlayıcı arayüzü.

Uygulama yalnızca MailProvider arayüzünü tanır; LLMClient'ta olduğu gibi.
Gmail sağlayıcısı OAuth kurulumu tamamlanınca bu arayüzü uygulayan tek bir
sınıf olarak eklenecek. O zamana kadar geliştirme ve demo için örnek
e-postalar döndüren DemoMailProvider var.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from . import models


@dataclass(frozen=True)
class MailMessage:
    """Sağlayıcıdan gelen ham e-posta (sağlayıcıdan bağımsız biçim)."""

    provider_id: str
    sender: str
    subject: str
    received_at: datetime
    body: str


class MailNotConfiguredError(Exception):
    """Bu kullanıcı ya da sunucu için posta bağlantısı yok."""


class MailAuthError(Exception):
    """Bağlantı geçersiz: izin geri alınmış ya da anahtarın süresi dolmuş."""


class MailFetchError(Exception):
    """Sağlayıcıya ulaşılamadı ya da beklenmedik yanıt verdi."""


class MailProvider(Protocol):
    def fetch_recent(
        self,
        user: models.User,
        days: int,
        known_ids: frozenset[str] = frozenset(),
    ) -> list[MailMessage]:
        """Son `days` gündeki e-postaları döndürür.

        known_ids: daha önce kaydedilmiş iletiler; sağlayıcı bunları yeniden
        indirmeyebilir (hem hız hem gizlilik için).
        """
        ...


class DemoMailProvider:
    """Geliştirme ve demo için hazır örnek e-postalar.

    Gerçek posta kutusu yerine geçer; içinde işle ilgisiz bir bülten de var
    ki ayıklama adımı gerçekten bir şey ayıklasın.
    """

    def fetch_recent(
        self,
        user: models.User,
        days: int,
        known_ids: frozenset[str] = frozenset(),
    ) -> list[MailMessage]:
        now = datetime.now(timezone.utc)
        samples = [
            (
                "demo-1",
                "Aselsan İnsan Kaynakları <ik@aselsan.com.tr>",
                "Backend Developer pozisyonu - mülakat daveti",
                1,
                "Merhaba, Backend Developer başvurunuz değerlendirildi. Sizi 25 Kasım "
                "saat 14:00'te çevrim içi teknik mülakata davet ediyoruz.",
            ),
            (
                "demo-2",
                "Getir Kariyer <careers@getir.com>",
                "Başvurunuz hakkında",
                3,
                "Python Developer pozisyonuna gösterdiğiniz ilgi için teşekkür ederiz. "
                "Bu aşamada başka adaylarla ilerlemeye karar verdik.",
            ),
            (
                "demo-3",
                "Trendyol Talent <talent@trendyol.com>",
                "Başvurunuz bize ulaştı",
                4,
                "Software Engineer Intern başvurunuzu aldık. Değerlendirme sürecinde "
                "size yeniden ulaşacağız.",
            ),
            (
                "demo-4",
                "Kahve Dükkanı <bulten@kahve.example>",
                "Bu hafta %20 indirim",
                2,
                "Tüm filtre kahvelerde indirim başladı, kaçırmayın.",
            ),
        ]
        return [
            MailMessage(pid, sender, subject, now - timedelta(days=ago), body)
            for pid, sender, subject, ago, body in samples
            if ago <= days
        ]


def get_mail_provider() -> MailProvider:
    """Gmail bağlı olmayan kullanıcılar için yedek sağlayıcı. MAIL_PROVIDER=demo."""
    kind = os.getenv("MAIL_PROVIDER", "").lower()
    if kind == "demo":
        return DemoMailProvider()
    raise MailNotConfiguredError(
        "Posta bağlantısı yapılandırılmadı. Geliştirme için MAIL_PROVIDER=demo kullan."
    )
