"""Posta kutusu uç noktaları: Gmail bağlantısı, tarama, listeleme, öneriyi kabul/ret."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import mail_classifier as mc
from . import history, models, schemas
from .ai import ask_model
from .auth import get_current_user
from .database import get_db
from .gmail import GmailProvider, GoogleOAuth, get_google_oauth
from .llm import LLMClient, get_llm_client
from .mail import (
    MailAuthError,
    MailFetchError,
    MailNotConfiguredError,
    MailProvider,
    get_mail_provider,
)
from .security import create_state_token, decode_state_token, decrypt_secret, encrypt_secret

router = APIRouter(prefix="/inbox", tags=["posta kutusu"])


def get_connection(db: Session, user: models.User) -> models.MailConnection | None:
    return db.scalar(
        select(models.MailConnection).where(models.MailConnection.owner_id == user.id)
    )


def mail_provider_or_503(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    oauth: GoogleOAuth | None = Depends(get_google_oauth),
) -> MailProvider:
    """Kullanıcının sağlayıcısını seçer: bağlı Gmail varsa o, yoksa demo.

    İkisi de yoksa anlaşılır bir 503 döndürür.
    """
    connection = get_connection(db, current_user)
    if connection is not None:
        if oauth is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gmail bağlı ama sunucuda Google ayarları eksik (GOOGLE_CLIENT_ID).",
            )
        refresh = decrypt_secret(connection.encrypted_refresh_token)
        if refresh is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Gmail anahtarı çözülemedi (şifreleme anahtarı değişmiş olabilir). Yeniden bağla.",
            )
        return GmailProvider(oauth, refresh)
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

    try:
        messages = provider.fetch_recent(current_user, days, frozenset(seen))
    except MailAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Gmail izni geri alınmış ya da süresi dolmuş. Hesabı yeniden bağla.",
        ) from exc
    except MailFetchError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
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

    connection = get_connection(db, current_user)
    if connection is not None:
        connection.last_synced_at = models.utcnow()
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

    history.record(db, application, email.suggested_status, models.ChangeSource.EPOSTA)
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


# --- Gmail bağlantısı ---


def frontend_url(result: str) -> str:
    base = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/?gmail={result}"


@router.get("/connection", response_model=schemas.MailConnectionStatus)
def connection_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    oauth: GoogleOAuth | None = Depends(get_google_oauth),
) -> schemas.MailConnectionStatus:
    connection = get_connection(db, current_user)
    demo = os.getenv("MAIL_PROVIDER", "").lower() == "demo"
    if connection is None:
        return schemas.MailConnectionStatus(
            connected=False, gmail_available=oauth is not None, demo_available=demo
        )
    return schemas.MailConnectionStatus(
        connected=True,
        provider=connection.provider,
        email_address=connection.email_address,
        connected_at=connection.connected_at,
        last_synced_at=connection.last_synced_at,
        gmail_available=oauth is not None,
        demo_available=demo,
    )


@router.get("/gmail/connect", response_model=schemas.AuthUrl)
def gmail_connect(
    current_user: models.User = Depends(get_current_user),
    oauth: GoogleOAuth | None = Depends(get_google_oauth),
) -> schemas.AuthUrl:
    """Google izin sayfasının adresini döndürür; frontend kullanıcıyı oraya yönlendirir.

    Doğrudan yönlendirme yapmıyoruz: bu istek Authorization başlığı taşımalı,
    tarayıcının adres çubuğundan gelen bir istek ise başlık taşıyamaz.
    """
    if oauth is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail bağlantısı sunucuda yapılandırılmadı (GOOGLE_CLIENT_ID / SECRET).",
        )
    return schemas.AuthUrl(auth_url=oauth.authorization_url(create_state_token(current_user.id)))


@router.get("/gmail/callback", include_in_schema=False)
def gmail_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    oauth: GoogleOAuth | None = Depends(get_google_oauth),
) -> RedirectResponse:
    """Google'ın döndüğü adres. Kullanıcıyı state belirtecinden tanırız."""
    if error or not code or not state or oauth is None:
        return RedirectResponse(frontend_url("iptal" if error == "access_denied" else "hata"))

    user_id = decode_state_token(state)
    user = db.get(models.User, user_id) if user_id is not None else None
    if user is None:
        return RedirectResponse(frontend_url("hata"))

    try:
        refresh = oauth.exchange_code(code)
        address = oauth.profile_email(oauth.access_token(refresh))
    except (MailAuthError, MailFetchError):
        return RedirectResponse(frontend_url("hata"))

    connection = get_connection(db, user)
    if connection is None:
        connection = models.MailConnection(owner_id=user.id, provider="gmail")
        db.add(connection)
    connection.email_address = address
    connection.encrypted_refresh_token = encrypt_secret(refresh)
    connection.connected_at = models.utcnow()
    db.commit()
    return RedirectResponse(frontend_url("baglandi"))


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(
    delete_emails: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    oauth: GoogleOAuth | None = Depends(get_google_oauth),
) -> Response:
    """Bağlantıyı kaldırır ve izni Google'da da geri alır.

    delete_emails=true ise kaydedilmiş e-posta özetleri de silinir.
    """
    connection = get_connection(db, current_user)
    if connection is not None:
        refresh = decrypt_secret(connection.encrypted_refresh_token)
        if oauth is not None and refresh:
            oauth.revoke(refresh)
        db.delete(connection)
    if delete_emails:
        db.execute(
            delete(models.EmailMessage).where(models.EmailMessage.owner_id == current_user.id)
        )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
