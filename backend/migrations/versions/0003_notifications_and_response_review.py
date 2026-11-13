"""notifications and clinician review of plan responses

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=40), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('ref_id', sa.Integer(), nullable=True),
        sa.Column('about_id', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)
    with op.batch_alter_table('plan_responses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reviewed_by', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('review_note', sa.String(length=300), nullable=True))
        batch_op.create_foreign_key('fk_plan_responses_reviewed_by', 'users', ['reviewed_by'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('plan_responses', schema=None) as batch_op:
        batch_op.drop_constraint('fk_plan_responses_reviewed_by', type_='foreignkey')
        batch_op.drop_column('review_note')
        batch_op.drop_column('reviewed_at')
        batch_op.drop_column('reviewed_by')
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notifications_user_id'))
    op.drop_table('notifications')
