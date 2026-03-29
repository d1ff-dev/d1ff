"""Initial schema with all tables and pgvector extension.

Revision ID: 001
Revises:
Create Date: 2026-03-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "installations",
        sa.Column("installation_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("account_login", sa.Text, nullable=False),
        sa.Column("account_type", sa.Text, nullable=False),
        sa.Column("suspended", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "installation_id",
            sa.Integer,
            sa.ForeignKey("installations.installation_id"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("encrypted_key", sa.Text, nullable=False),
        sa.Column("custom_endpoint", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("installation_id", "provider"),
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column(
            "installation_id",
            sa.Integer,
            sa.ForeignKey("installations.installation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repo_name", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("private", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "pr_states",
        sa.Column("installation_id", sa.Integer, nullable=False),
        sa.Column("repo_full_name", sa.Text, nullable=False),
        sa.Column("pr_number", sa.Integer, nullable=False),
        sa.Column("state", sa.Text, nullable=False, server_default="active"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("installation_id", "repo_full_name", "pr_number"),
    )

    op.create_table(
        "feedback_reactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("comment_id", sa.Integer, nullable=False),
        sa.Column("reaction_type", sa.Text, nullable=False),
        sa.Column("installation_id", sa.Integer, nullable=False),
        sa.Column("pr_number", sa.Integer, nullable=False),
        sa.Column("repo_full_name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("github_id", sa.Integer, unique=True, nullable=False),
        sa.Column("login", sa.Text, nullable=False),
        sa.Column("email", sa.Text),
        sa.Column("avatar_url", sa.Text),
        sa.Column("encrypted_token", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_installations",
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "installation_id",
            sa.Integer,
            sa.ForeignKey("installations.installation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "installation_id"),
    )

    op.create_table(
        "user_global_settings",
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("custom_endpoint", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_global_settings")
    op.drop_table("user_installations")
    op.drop_table("users")
    op.drop_table("feedback_reactions")
    op.drop_table("pr_states")
    op.drop_table("repositories")
    op.drop_table("api_keys")
    op.drop_table("installations")
    op.execute("DROP EXTENSION IF EXISTS vector")
