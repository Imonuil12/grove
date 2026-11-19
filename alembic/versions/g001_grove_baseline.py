"""Grove baseline: accounts and the coach.

Replaces the pre-Grove (medication app) migration history. Databases created by
that history are converted by manage_db.py, which keeps users and passwords.

Revision ID: g001
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "g001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("profile_data", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "local_credentials",
        sa.Column("credential_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_local_credential_user"),
        sa.PrimaryKeyConstraint("credential_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_local_credentials_email", "local_credentials", ["email"], unique=True)

    op.create_table(
        "coach_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_coach_conversation_user", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coach_conversations_public_id", "coach_conversations", ["public_id"], unique=True)
    op.create_index("ix_coach_conversations_user_id", "coach_conversations", ["user_id"])

    op.create_table(
        "coach_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["coach_conversations.id"],
                                name="fk_coach_message_conversation", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coach_messages_conversation_id", "coach_messages", ["conversation_id"])


def downgrade():
    op.drop_table("coach_messages")
    op.drop_table("coach_conversations")
    op.drop_table("local_credentials")
    op.drop_table("users")
