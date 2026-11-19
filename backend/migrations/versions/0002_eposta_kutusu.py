"""E-posta kutusu: işle ilgili e-postalar ve durum önerileri

Revizyon: 0002
Önceki: 0001
Tarih: 2026-11-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(length=200), nullable=False),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("suggested_status", sa.String(length=20), nullable=True),
        sa.Column("suggestion_state", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_emails_owner_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_emails_application_id_applications"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emails")),
        sa.UniqueConstraint("owner_id", "provider_id", name=op.f("uq_emails_owner_id")),
    )
    op.create_index(op.f("ix_emails_owner_id"), "emails", ["owner_id"])
    op.create_index(op.f("ix_emails_received_at"), "emails", ["received_at"])
    op.create_index(op.f("ix_emails_application_id"), "emails", ["application_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_emails_application_id"), table_name="emails")
    op.drop_index(op.f("ix_emails_received_at"), table_name="emails")
    op.drop_index(op.f("ix_emails_owner_id"), table_name="emails")
    op.drop_table("emails")
