"""add chat memory

Revision ID: e1614c7dfac1
Revises: 3377e7622ca6
Create Date: 2026-05-15 01:24:55.632745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1614c7dfac1'
down_revision: Union[str, Sequence[str], None] = '3377e7622ca6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('chat_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_sessions_case_id'), 'chat_sessions', ['case_id'], unique=False)

    op.create_table('chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),  # 'user' or 'assistant'
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_session_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_chat_sessions_case_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')