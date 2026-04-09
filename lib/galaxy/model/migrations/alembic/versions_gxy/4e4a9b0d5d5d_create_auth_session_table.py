"""create auth_session table

Revision ID: 4e4a9b0d5d5d
Revises: f5e9e4bca542
Create Date: 2026-04-09 18:00:00.000000

"""

import sqlalchemy as sa

from galaxy.model.migrations.util import (
    create_table,
    drop_table,
)

# revision identifiers, used by Alembic.
revision = "4e4a9b0d5d5d"
down_revision = "f5e9e4bca542"
branch_labels = None
depends_on = None


def upgrade():
    create_table(
        "auth_session",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("galaxy_user.id"), index=True),
        sa.Column("impersonator_user_id", sa.Integer, sa.ForeignKey("galaxy_user.id"), index=True),
        sa.Column("remote_host", sa.String(255)),
        sa.Column("remote_addr", sa.String(255)),
        sa.Column("referer", sa.TEXT),
        sa.Column("current_history_id", sa.Integer, sa.ForeignKey("history.id"), index=True),
        sa.Column("session_type", sa.String(32), nullable=False, index=True),
        sa.Column("auth_source", sa.String(32), nullable=False, index=True),
        sa.Column("refresh_token_hash", sa.String(255), unique=True, index=True),
        sa.Column("refresh_token_iat", sa.DateTime, nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime, nullable=True, index=True),
        sa.Column("is_valid", sa.Boolean, nullable=False, index=True),
        sa.Column("last_activity", sa.DateTime, nullable=True, index=True),
        sa.Column("impersonation_started_at", sa.DateTime, nullable=True),
    )


def downgrade():
    drop_table("auth_session")
