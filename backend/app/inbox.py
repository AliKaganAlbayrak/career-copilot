"""Posta kutusu uç noktaları: tarama, listeleme, öneriyi kabul/ret."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import mail_classifier as mc
from . import models, schemas
from .ai import ask_model
from .auth import get_current_user
from .database import get_db
from .llm import LLMClient, get_llm_client
from .mail import MailNotConfiguredError, MailProvider, get_mail_provider

router = APIRouter(prefix="/inbox", tags=["posta kutusu"])


def mail_provider_or_503() -> MailProvider:
    """Sağlayıcı yapılandırılmamışsa anlaşılır bir 503 döndürür."""
    try:
        return get_mail_provider()
    except MailNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def get_email_or_404(email_id: int, db: Session, owner: models.User) -> models.EmailMessage:
    email = db.get(models.EmailMessage, email_id)
    if email is None or email.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="E-posta bulunamadı.")
    return email


@router.post("/sync", response_model=schemas.SyncResult)
def sync(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    provider: MailProvider = Depends(mail_provider_or_503),
    llm: LLMClient = Depends(get_llm_client),
) -> schemas.SyncResult:
    """Son N günün e-postalarını tarar, işle ilgili olanları kaydeder."""
    applications = db.scalars(
        select(models.Application)
        .where(models.Application.owner_id == current_user.id)
        .order_by(models.Application.applied_at.desc())  # aynı şirkete birden çok başvuruda en yenisi
    ).all()
    companies = {a.id: a.company for a in applications}
    company_names = list(dict.fromkeys(companies.values()))

    seen = set(
        db.scalars(
            select(models.EmailMessage.provider_id).where(
                models.EmailMessage.owner_id == current_user.id
            )
        )
    )

    messages = provider.fetch_recent(current_user, days)
    job_related = 0
    new = 0
    for message in messages:
        if message.provider_id in seen:
            job_related += 1  # daha önce işle ilgili bulunup kaydedilmişti
            continue
        if not mc.looks_job_related(message, company_names):
            continue  # modele hiç gitmez

        raw = ask_model(
            llm,
            mc.build_classify_prompt(message, company_names),
            system=mc.CLASSIFY_SYSTEM,
            json_mode=True,
        )
        try:
            result = mc.parse_classification(raw)
        except ValueError:
            continue  # tek bir bozuk yanıt tüm taramayı durdurmasın
        if not result.is_job_related:
            continue

        application_id = mc.match_company(result, message, companies)
        suggested = mc.SUGGESTED_STATUS[result.category] if application_id else None
        # Başvuru zaten o durumdaysa önerecek bir şey yok.
        if suggested and companies and application_id is not None:
            current = next(a.status for a in applications if a.id == application_id)
            if current == suggested:
                suggested = None

        db.add(
            models.EmailMessage(
                owner_id=current_user.id,
                provider_id=message.provider_id,
                sender=message.sender[:320],
                subject=message.subject[:500],
                received_at=message.received_at,
                category=result.category,
                summary=result.summary or message.subject,
                company=result.company,
                application_id=application_id,
                suggested_status=suggested,
                suggestion_state=(
                    models.SuggestionState.BEKLIYOR.value
                    if suggested
                    else models.SuggestionState.YOK.value
                ),
            )
        )
        seen.add(message.provider_id)
        job_related += 1
        new += 1

    db.commit()
    return schemas.SyncResult(scanned=len(messages), job_related=job_related, new=new)


@router.get("", response_model=list[schemas.Email])
def list_emails(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[models.EmailMessage]:
    """İşle ilgili e-postalar, en yeniden eskiye."""
    return list(
        db.scalars(
            select(models.EmailMessage)
            .where(models.EmailMessage.owner_id == current_user.id)
            .order_by(models.EmailMessage.received_at.desc())
        )
    )


def _pending_or_400(email: models.EmailMessage) -> None:
    if email.suggestion_state != models.SuggestionState.BEKLIYOR.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta için bekleyen bir öneri yok.",
        )


@router.post("/{email_id}/accept", response_model=schemas.Email)
def accept_suggestion(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.EmailMessage:
    """Öneriyi uygular: bağlı başvurunun durumunu değiştirir.

    Durum asla kendiliğinden değişmez; e-posta yanlış okunmuş olabilir,
    son kararı kullanıcı verir.
    """
    email = get_email_or_404(email_id, db, current_user)
    _pending_or_400(email)

    application = db.get(models.Application, email.application_id) if email.application_id else None
    if application is None or application.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bağlı başvuru artık yok; öneri uygulanamaz.",
        )

    application.status = email.suggested_status
    email.suggestion_state = models.SuggestionState.KABUL.value
    db.commit()
    db.refresh(email)
    return email


@router.post("/{email_id}/dismiss", response_model=schemas.Email)
def dismiss_suggestion(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.EmailMessage:
    """Öneriyi yok sayar; başvuru olduğu gibi kalır."""
    email = get_email_or_404(email_id, db, current_user)
    _pending_or_400(email)
    email.suggestion_state = models.SuggestionState.YOKSAYILDI.value
    db.commit()
    db.refresh(email)
    return email
