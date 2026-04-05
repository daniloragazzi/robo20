"""candles_hypertable

Revision ID: 108f2e33f9b1
Revises: 9bd0cb270ce2
Create Date: 2026-04-03 21:54:22.297685
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '108f2e33f9b1'
down_revision: Union[str, None] = '9bd0cb270ce2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
    # Convert candles table to a hypertable partitioned by ts
    op.execute(
        "SELECT create_hypertable('candles', 'ts', "
        "if_not_exists => TRUE, "
        "migrate_data => TRUE);"
    )


def downgrade() -> None:
    # TimescaleDB does not support converting back to a regular table.
    # The table itself remains, just not optimized.
    pass
