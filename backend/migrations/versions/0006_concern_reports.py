"""concern reports and their events

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('concern_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('participant_id', sa.String(length=40), nullable=False),
        sa.Column('recipient_id', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=14), nullable=False),
        sa.Column('topic', sa.String(length=24), nullable=False),
        sa.Column('since', sa.String(length=14), nullable=False),
        sa.Column('text', sa.String(length=600), nullable=False),
        sa.Column('rev', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['participant_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('concern_reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_concern_reports_participant_id'), ['participant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_concern_reports_recipient_id'), ['recipient_id'], unique=False)
    op.create_table('concern_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=14), nullable=False),
        sa.Column('actor_id', sa.String(length=40), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['report_id'], ['concern_reports.id'], ),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('concern_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_concern_events_report_id'), ['report_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('concern_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_concern_events_report_id'))
    op.drop_table('concern_events')
    with op.batch_alter_table('concern_reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_concern_reports_recipient_id'))
        batch_op.drop_index(batch_op.f('ix_concern_reports_participant_id'))
    op.drop_table('concern_reports')
