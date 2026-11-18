"""Göçlerin doğruluğu: boş veritabanına uygulanan göçler, modellerle
birebir aynı şemayı üretmeli. Biri modeli değiştirip göç yazmayı
unutursa bu test kırılır."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.database import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config(connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["connection"] = connection
    return config


def test_gocler_modellerle_ayni_semayi_uretir(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'goc.db'}")
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "head")

        farklar = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert farklar == [], f"Modeller ile göçler uyuşmuyor: {farklar}"


def test_gocler_geri_alinabilir(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'goc.db'}")
    with engine.begin() as connection:
        config = alembic_config(connection)
        command.upgrade(config, "head")
        command.downgrade(config, "base")

        tablolar = set(inspect(connection).get_table_names())

    # Geriye yalnızca Alembic'in kendi sürüm tablosu kalmalı.
    assert tablolar <= {"alembic_version"}
