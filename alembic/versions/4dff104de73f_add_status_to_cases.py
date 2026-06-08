"""add status to cases

Revision ID: 4dff104de73f
Revises: e1614c7dfac1
Create Date: 2026-06-05 00:45:20.903594

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dff104de73f'
down_revision: Union[str, Sequence[str], None] = 'e1614c7dfac1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cases', sa.Column('status', sa.String(20), nullable=False, server_default='pending'))

def downgrade() -> None:
    op.drop_column('cases', 'status')