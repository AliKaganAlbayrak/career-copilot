"""Veritabanı bağlantısı ve oturum yönetimi.

SQLite ile başlıyoruz; ileride PostgreSQL'e geçerken sadece
DATABASE_URL'in değişmesi yeterli olacak şekilde kurgulandı.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Ortam değişkeni varsa onu kullan, yoksa yerel SQLite dosyası.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./career.db")

# check_same_thread yalnızca SQLite için gerekli: FastAPI isteği
# başka bir thread'de işleyebildiği için bu kısıtı kapatıyoruz.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Kısıtlara (index, unique, foreign key...) öngörülebilir adlar verir.
# Adsız kısıtlar göç yazarken sorun çıkarır: silmek ya da değiştirmek için
# adını bilmen gerekir ve SQLite adsız kısıtları göçlerde yönetemez.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Tüm ORM modellerinin türeyeceği taban sınıf."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db() -> Generator[Session, None, None]:
    """İstek başına bir veritabanı oturumu açar ve sonunda kapatır."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
