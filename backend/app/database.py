"""Veritabanı bağlantısı ve oturum yönetimi.

SQLite ile başlıyoruz; ileride PostgreSQL'e geçerken sadece
DATABASE_URL'in değişmesi yeterli olacak şekilde kurgulandı.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Ortam değişkeni varsa onu kullan, yoksa yerel SQLite dosyası.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./career.db")

# check_same_thread yalnızca SQLite için gerekli: FastAPI isteği
# başka bir thread'de işleyebildiği için bu kısıtı kapatıyoruz.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Tüm ORM modellerinin türeyeceği taban sınıf."""


def get_db() -> Generator[Session, None, None]:
    """İstek başına bir veritabanı oturumu açar ve sonunda kapatır."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
