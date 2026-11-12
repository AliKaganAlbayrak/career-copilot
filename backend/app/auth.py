"""Kimlik doğrulama: kayıt, giriş ve 'şu anki kullanıcı' bağımlılığı."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .security import create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["kimlik"])

# İstekteki "Authorization: Bearer <token>" başlığını okur.
# tokenUrl sayesinde /docs sayfasındaki "Authorize" düğmesi de çalışır.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Belirteci doğrular ve sahibini döndürür; geçersizse 401 fırlatır.

    Korunan her uç nokta bunu Depends ile ister.
    """
    user_id = decode_access_token(token)
    user = db.get(models.User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum geçersiz veya süresi dolmuş.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)) -> models.User:
    """Yeni kullanıcı oluşturur. E-posta zaten kayıtlıysa 409 döner."""
    email = payload.email.lower()
    if db.scalar(select(models.User).where(models.User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta adresi zaten kayıtlı.",
        )

    user = models.User(email=email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> schemas.Token:
    """E-posta + parola ile giriş. OAuth2 standardı gereği alan adı 'username'."""
    user = db.scalar(select(models.User).where(models.User.email == form.username.lower()))

    # Hangi bilginin yanlış olduğunu söylemiyoruz: saldırgana ipucu vermemek için.
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya parola hatalı.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return schemas.Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=schemas.User)
def me(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Oturum açmış kullanıcının bilgileri."""
    return current_user
