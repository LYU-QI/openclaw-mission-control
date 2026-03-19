"""Add default_approval_policy to feishu_sync_configs table.

Revision ID: add_approval_policy
Revises:
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_approval_policy'
down_revision = '1d3ae6e0cdfd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'feishu_sync_configs',
        sa.Column('default_approval_policy', sa.String(), nullable=True, server_default='auto')
    )


def downgrade() -> None:
    op.drop_column('feishu_sync_configs', 'default_approval_policy')
