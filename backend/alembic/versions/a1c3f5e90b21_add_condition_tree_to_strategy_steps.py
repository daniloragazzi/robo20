"""add_condition_tree_to_strategy_steps

Revision ID: a1c3f5e90b21
Revises: 035d8520a235
Create Date: 2026-04-05 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1c3f5e90b21'
down_revision: Union[str, None] = '035d8520a235'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'strategy_steps',
        sa.Column('condition_tree', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('strategy_steps', 'condition_tree')
