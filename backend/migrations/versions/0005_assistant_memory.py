"""assistant conversation memory

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('assistant_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=40), nullable=False),
        sa.Column('who', sa.String(length=4), nullable=False),
        sa.Column('text', sa.String(length=300), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('ctx', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('assistant_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assistant_messages_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_assistant_messages_created_at'), ['created_at'], unique=False)
    with op.batch_alter_table('patient_preferences', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assistant_memory', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table('patient_preferences', schema=None) as batch_op:
        batch_op.drop_column('assistant_memory')
    with op.batch_alter_table('assistant_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assistant_messages_created_at'))
        batch_op.drop_index(batch_op.f('ix_assistant_messages_user_id'))
    op.drop_table('assistant_messages')
