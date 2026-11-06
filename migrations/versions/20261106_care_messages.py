"""Patient-bound direct care messages and explicit opening acknowledgements."""

import sqlalchemy as sa
from alembic import op

revision = "20261106_care_messages"
down_revision = "89ffe14db4cd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "care_messages",
        sa.Column("id", sa.String(60), primary_key=True),
        sa.Column(
            "patient_id", sa.String(60), sa.ForeignKey("patients.id"), nullable=False
        ),
        sa.Column(
            "sender_id", sa.String(60), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "recipient_id", sa.String(60), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("command_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.String(50), nullable=False),
        sa.Column("opened_at", sa.String(50), nullable=True),
        sa.UniqueConstraint("sender_id", "command_id", name="uq_care_message_command"),
    )
    op.create_index("ix_care_messages_patient_id", "care_messages", ["patient_id"])
    op.create_index(
        "ix_care_message_conversation",
        "care_messages",
        ["patient_id", "sender_id", "recipient_id", "created_at", "id"],
    )


def downgrade():
    op.drop_table("care_messages")
