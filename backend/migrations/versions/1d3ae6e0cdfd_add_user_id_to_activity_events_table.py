"""Add user_id to activity_events table

Revision ID: 1d3ae6e0cdfd
Revises: 85ef1026071d
Create Date: 2026-03-15 13:19:41.042068

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1d3ae6e0cdfd'
down_revision = '85ef1026071d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id column to activity_events table
    op.add_column('activity_events', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_activity_events_user_id'), 'activity_events', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop user_id column from activity_events table
    op.drop_index(op.f('ix_activity_events_user_id'), table_name='activity_events')
    op.drop_column('activity_events', 'user_id')