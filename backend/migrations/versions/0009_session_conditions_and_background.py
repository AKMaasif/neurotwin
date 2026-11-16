"""Today's conditions on activity sessions, and the person's education and first language. Existing rows read "not asked".

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def _have(table: str) -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # activity_sessions is a baseline table: on a database from before migrations, start-up makes it from the current model,
    # so the columns may already be there. Add only what is missing.
    have = _have('activity_sessions')
    with op.batch_alter_table('activity_sessions', schema=None) as b:
        for name in ('see_clearly', 'hear_clearly', 'slept_well', 'quiet_place'):
            if name not in have:
                b.add_column(sa.Column(name, sa.Boolean(), nullable=True))
    have = _have('patient_preferences')
    with op.batch_alter_table('patient_preferences', schema=None) as b:
        for name in ('education', 'first_language'):
            if name not in have:
                b.add_column(sa.Column(name, sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('patient_preferences', schema=None) as b:
        b.drop_column('first_language')
        b.drop_column('education')
    with op.batch_alter_table('activity_sessions', schema=None) as b:
        for name in ('quiet_place', 'slept_well', 'hear_clearly', 'see_clearly'):
            b.drop_column(name)
