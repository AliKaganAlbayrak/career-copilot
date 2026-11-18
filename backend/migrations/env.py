"""Alembic çalışma ortamı: göçleri uygulamanın veritabanına bağlar."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

# models'i içe aktarmak tabloları Base.metadata'ya kaydeder;
# autogenerate ve "alembic check" modelleri buradan okur.
from app import models  # noqa: F401
from app.database import Base, engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Veritabanına bağlanmadan SQL çıktısı üretir (alembic upgrade --sql)."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Göçleri doğrudan veritabanına uygular."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite ALTER TABLE'ı çok sınırlı destekler. Batch modu tabloyu
            # yeniden oluşturarak sütun silme/değiştirme işlerini mümkün kılar.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
