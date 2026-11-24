"""Durum geçmişi: her başvurunun durum değişiklikleri

Mevcut başvurular için geçmiş yok; her birine şu anki durumunu başvuru
tarihinde almış gibi tek bir başlangıç kaydı eklenir (veri göçü).

Revizyon: 0004
Önceki: 0003
Tarih: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "status_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_status_changes_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_status_changes")),
    )
    op.create_index(op.f("ix_status_changes_application_id"), "status_changes", ["application_id"])
    op.create_index(op.f("ix_status_changes_changed_at"), "status_changes", ["changed_at"])

    # Veri göçü: şema göçü tabloyu kurar, bu satır da var olan veriyi taşır.
    # Düz SQL, SQLite ve PostgreSQL'de aynı çalışır.
    op.execute(
        "INSERT INTO status_changes (application_id, from_status, to_status, source, changed_at) "
        "SELECT id, NULL, status, 'olusturma', applied_at FROM applications"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_status_changes_changed_at"), table_name="status_changes")
    op.drop_index(op.f("ix_status_changes_application_id"), table_name="status_changes")
    op.drop_table("status_changes")
