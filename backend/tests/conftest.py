"""Test altyapısı: her test kendi boş veritabanıyla çalışır."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    """Gerçek veritabanı yerine teste özel SQLite kullanan istemci."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def kayit_ve_giris(client: TestClient, email: str, password: str = "gizli-parola-1") -> dict[str, str]:
    """Kullanıcı oluşturur, giriş yapar ve Authorization başlığını döndürür."""
    client.post("/auth/register", json={"email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def auth_client(client: TestClient) -> TestClient:
    """Oturum açmış istemci: her isteğe belirteci kendiliğinden ekler."""
    client.headers.update(kayit_ve_giris(client, "ali@example.com"))
    return client
