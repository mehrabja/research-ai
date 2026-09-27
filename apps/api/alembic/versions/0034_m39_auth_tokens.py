"""M39 F02 — verification/reset token persistence and user verification state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    for table in ("email_verification_tokens", "password_reset_tokens"):
        op.create_table(
            table,
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "used_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
    op.create_index(
        "ix_email_verification_tokens_user",
        "email_verification_tokens",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_email_verification_tokens_active",
        "email_verification_tokens",
        ["user_id", "used_at", "expires_at"],
    )
    op.create_index(
        "ix_password_reset_tokens_user",
        "password_reset_tokens",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_password_reset_tokens_active",
        "password_reset_tokens",
        ["user_id", "used_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_tokens_active",
        table_name="password_reset_tokens",
    )
    op.drop_index(
        "ix_password_reset_tokens_user",
        table_name="password_reset_tokens",
    )
    op.drop_index(
        "ix_email_verification_tokens_active",
        table_name="email_verification_tokens",
    )
    op.drop_index(
        "ix_email_verification_tokens_user",
        table_name="email_verification_tokens",
    )
    op.drop_table("password_reset_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified_at")
