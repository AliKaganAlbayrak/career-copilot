"""İlk şema: kullanıcılar ve başvurular

Revizyon: 0001
Önceki: yok
Tarih: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("hashed_password", sa.String(length=200), nullable=False),
        sa.Column("cv_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_applications_owner_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
    )
    op.create_index(op.f("ix_applications_owner_id"), "applications", ["owner_id"])
    op.create_index(op.f("ix_applications_company"), "applications", ["company"])
    op.create_index(op.f("ix_applications_status"), "applications", ["status"])
    op.create_index(op.f("ix_applications_applied_at"), "applications", ["applied_at"])


def downgrade() -> None:
    # Ters sırayla: önce başvurular (kullanıcılara bağlı), sonra kullanıcılar.
    op.drop_index(op.f("ix_applications_applied_at"), table_name="applications")
    op.drop_index(op.f("ix_applications_status"), table_name="applications")
    op.drop_index(op.f("ix_applications_company"), table_name="applications")
    op.drop_index(op.f("ix_applications_owner_id"), table_name="applications")
    op.drop_table("applications")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
