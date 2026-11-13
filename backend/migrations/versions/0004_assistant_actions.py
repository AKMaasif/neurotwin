"""assistant actions waiting for confirmation

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('assistant_actions',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=40), nullable=False),
        sa.Column('tool', sa.String(length=30), nullable=False),
        sa.Column('args', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('outcome', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('assistant_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assistant_actions_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('assistant_actions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assistant_actions_user_id'))
    op.drop_table('assistant_actions')
