"""PCM voice-note storage and message metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20261106_voice_notes"
down_revision = "20261106_care_messages"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "care_messages",
        sa.Column("media", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "care_audio",
        sa.Column(
            "message_id",
            sa.String(60),
            sa.ForeignKey("care_messages.id"),
            primary_key=True,
        ),
        sa.Column("data", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("care_audio")
    op.drop_column("care_messages", "media")
