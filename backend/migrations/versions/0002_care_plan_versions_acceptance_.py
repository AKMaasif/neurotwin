"""care plan versions, acceptance, structured items, preferences

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13 19:07:38.701368
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _adopt_existing_routines() -> None:
    """Routines written before acceptance existed are kept exactly as they were: each person's routines become version 1 of a plan that is
    marked legacy and accepted, so nothing disappears from anyone's Today list. New plans need real acceptance."""
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT participant_id, MIN(created_by), MIN(created_at) FROM care_plan_items GROUP BY participant_id")).all()
    for pid, creator, created in rows:
        bind.execute(sa.text("INSERT INTO care_plans (participant_id, version, status, created_by, created_at, sent_by, sent_at, responded_at, legacy) "
                             "VALUES (:p, 1, 'accepted', :c, :t, :c, :t, :t, :l)"), {"p": pid, "c": creator, "t": created, "l": True})
        plan_id = bind.execute(sa.text("SELECT MAX(id) FROM care_plans WHERE participant_id = :p"), {"p": pid}).scalar()
        bind.execute(sa.text("UPDATE care_plan_items SET plan_id = :i WHERE participant_id = :p"), {"i": plan_id, "p": pid})


def upgrade() -> None:
    op.create_table('care_plans',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('participant_id', sa.String(length=40), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('created_by', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_by', sa.String(length=40), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('supersedes_id', sa.Integer(), nullable=True),
    sa.Column('legacy', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['participant_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sent_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['supersedes_id'], ['care_plans.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('care_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_care_plans_participant_id'), ['participant_id'], unique=False)

    op.create_table('patient_preferences',
    sa.Column('user_id', sa.String(length=40), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('plan_responses',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('plan_id', sa.Integer(), nullable=False),
    sa.Column('participant_id', sa.String(length=40), nullable=False),
    sa.Column('response', sa.String(length=10), nullable=False),
    sa.Column('note', sa.String(length=300), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['participant_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['plan_id'], ['care_plans.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('plan_responses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plan_responses_participant_id'), ['participant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_plan_responses_plan_id'), ['plan_id'], unique=False)

    if 'plan_id' not in _cols('care_plan_items'):   # a table made fresh by the adoption step already has these
        with op.batch_alter_table('care_plan_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('plan_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('title', sa.String(length=120), nullable=True))
            batch_op.add_column(sa.Column('time_hhmm', sa.String(length=5), nullable=True))
            batch_op.add_column(sa.Column('window_start', sa.String(length=5), nullable=True))
            batch_op.add_column(sa.Column('window_end', sa.String(length=5), nullable=True))
            batch_op.add_column(sa.Column('start_date', sa.String(length=10), nullable=True))
            batch_op.add_column(sa.Column('end_date', sa.String(length=10), nullable=True))
            batch_op.add_column(sa.Column('quantity', sa.Float(), nullable=True))
            batch_op.add_column(sa.Column('unit', sa.String(length=20), nullable=True))
            batch_op.add_column(sa.Column('precautions', sa.String(length=300), nullable=True))
            batch_op.add_column(sa.Column('copied_from_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('extraction', sa.JSON(), nullable=True))
            batch_op.create_index(batch_op.f('ix_care_plan_items_plan_id'), ['plan_id'], unique=False)
            batch_op.create_foreign_key('fk_care_plan_items_plan_id', 'care_plans', ['plan_id'], ['id'])

    _adopt_existing_routines()

    if 'until' not in _cols('care_plan_replies'):
        with op.batch_alter_table('care_plan_replies', schema=None) as batch_op:
            batch_op.add_column(sa.Column('until', sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column('reason', sa.String(length=20), nullable=True))
            batch_op.add_column(sa.Column('note', sa.String(length=200), nullable=True))
            batch_op.add_column(sa.Column('idem_key', sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column('recorded_by', sa.String(length=40), nullable=True))
            batch_op.create_unique_constraint('uq_care_plan_replies_idem_key', ['idem_key'])


def downgrade() -> None:
    with op.batch_alter_table('care_plan_replies', schema=None) as batch_op:
        batch_op.drop_constraint('uq_care_plan_replies_idem_key', type_='unique')
        batch_op.drop_column('recorded_by')
        batch_op.drop_column('idem_key')
        batch_op.drop_column('note')
        batch_op.drop_column('reason')
        batch_op.drop_column('until')

    with op.batch_alter_table('care_plan_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_care_plan_items_plan_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_care_plan_items_plan_id'))
        batch_op.drop_column('extraction')
        batch_op.drop_column('copied_from_id')
        batch_op.drop_column('precautions')
        batch_op.drop_column('unit')
        batch_op.drop_column('quantity')
        batch_op.drop_column('end_date')
        batch_op.drop_column('start_date')
        batch_op.drop_column('window_end')
        batch_op.drop_column('window_start')
        batch_op.drop_column('time_hhmm')
        batch_op.drop_column('title')
        batch_op.drop_column('plan_id')

    with op.batch_alter_table('plan_responses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plan_responses_plan_id'))
        batch_op.drop_index(batch_op.f('ix_plan_responses_participant_id'))

    op.drop_table('plan_responses')
    op.drop_table('patient_preferences')
    with op.batch_alter_table('care_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_care_plans_participant_id'))

    op.drop_table('care_plans')
