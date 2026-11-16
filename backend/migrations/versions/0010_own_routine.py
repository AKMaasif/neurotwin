"""The person's own daily routine, saved from an assistant draft (separate from the clinician's care plan).

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # patient_preferences may have been made from the current model at start-up on an old database: add only what is missing.
    have = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('patient_preferences')}
    if 'own_routine' not in have:
        with op.batch_alter_table('patient_preferences', schema=None) as b:
            b.add_column(sa.Column('own_routine', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('patient_preferences', schema=None) as b:
        b.drop_column('own_routine')
