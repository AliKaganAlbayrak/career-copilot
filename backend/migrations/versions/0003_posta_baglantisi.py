"""Posta bağlantısı: kullanıcı başına şifreli Gmail anahtarı

Revizyon: 0003
Önceki: 0002
Tarih: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mail_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_mail_connections_owner_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_connections")),
    )
    # Kullanıcı başına tek bağlantı.
    op.create_index(
        op.f("ix_mail_connections_owner_id"), "mail_connections", ["owner_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mail_connections_owner_id"), table_name="mail_connections")
    op.drop_table("mail_connections")
