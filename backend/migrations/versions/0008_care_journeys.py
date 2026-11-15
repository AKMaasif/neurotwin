"""Add linked care journeys and append-only follow-up events. Existing rows are untouched."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("care_journeys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("concern_id", sa.Integer(), sa.ForeignKey("concern_reports.id"), nullable=False, unique=True),
        sa.Column("participant_id", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("clinician_id", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("care_plans.id"), nullable=True),
        sa.Column("analysis_run_id", sa.String(32), nullable=True),
        sa.Column("analysis_digest", sa.String(64), nullable=True),
        sa.Column("next_action", sa.String(300), nullable=False),
        sa.Column("follow_up_on", sa.String(10), nullable=True),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_care_journeys_participant_id", "care_journeys", ["participant_id"])
    op.create_table("care_journey_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("journey_id", sa.Integer(), sa.ForeignKey("care_journeys.id"), nullable=False),
        sa.Column("actor_id", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_care_journey_events_journey_id", "care_journey_events", ["journey_id"])


def downgrade():
    op.drop_table("care_journey_events")
    op.drop_table("care_journeys")
