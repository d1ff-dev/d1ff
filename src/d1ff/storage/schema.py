"""SQLAlchemy Core table declarations — single source of truth for DB schema."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()

installations = Table(
    "installations",
    metadata,
    Column("installation_id", Integer, primary_key=True, autoincrement=False),
    Column("account_login", Text, nullable=False),
    Column("account_type", Text, nullable=False),
    Column("suspended", Boolean, nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

api_keys = Table(
    "api_keys",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "installation_id",
        Integer,
        ForeignKey("installations.installation_id"),
        nullable=False,
    ),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("encrypted_key", Text, nullable=False),
    Column("custom_endpoint", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("installation_id", "provider"),
)

repositories = Table(
    "repositories",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column(
        "installation_id",
        Integer,
        ForeignKey("installations.installation_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("repo_name", Text, nullable=False),
    Column("full_name", Text, nullable=False),
    Column("private", Boolean, nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

pr_states = Table(
    "pr_states",
    metadata,
    Column("installation_id", Integer, nullable=False),
    Column("repo_full_name", Text, nullable=False),
    Column("pr_number", Integer, nullable=False),
    Column("state", Text, nullable=False, server_default="active"),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("installation_id", "repo_full_name", "pr_number"),
)

feedback_reactions = Table(
    "feedback_reactions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("comment_id", Integer, nullable=False),
    Column("reaction_type", Text, nullable=False),
    Column("installation_id", Integer, nullable=False),
    Column("pr_number", Integer, nullable=False),
    Column("repo_full_name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("github_id", Integer, unique=True, nullable=False),
    Column("login", Text, nullable=False),
    Column("email", Text),
    Column("avatar_url", Text),
    Column("encrypted_token", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

user_installations = Table(
    "user_installations",
    metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "installation_id",
        Integer,
        ForeignKey("installations.installation_id", ondelete="CASCADE"),
        nullable=False,
    ),
    PrimaryKeyConstraint("user_id", "installation_id"),
)

user_global_settings = Table(
    "user_global_settings",
    metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("encrypted_api_key", Text, nullable=False),
    Column("custom_endpoint", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
