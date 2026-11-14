"""trusted contact for the emergency screen

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('patient_preferences', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trusted_name', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('trusted_phone', sa.String(length=24), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('patient_preferences', schema=None) as batch_op:
        batch_op.drop_column('trusted_phone')
        batch_op.drop_column('trusted_name')
