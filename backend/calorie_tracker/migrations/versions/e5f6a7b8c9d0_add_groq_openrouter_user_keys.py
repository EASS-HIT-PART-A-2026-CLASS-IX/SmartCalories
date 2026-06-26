"""add groq + openrouter key columns to user_llm_key

Lets users store personal Groq and OpenRouter keys alongside Anthropic + Gemini, so the chat
agent can fall through all four providers (in that order) on a user's own quota. All nullable.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_llm_key',
        sa.Column('groq_key_enc', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
    )
    op.add_column(
        'user_llm_key',
        sa.Column('groq_key_last4', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
    )
    op.add_column(
        'user_llm_key',
        sa.Column('openrouter_key_enc', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
    )
    op.add_column(
        'user_llm_key',
        sa.Column('openrouter_key_last4', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('user_llm_key', 'openrouter_key_last4')
    op.drop_column('user_llm_key', 'openrouter_key_enc')
    op.drop_column('user_llm_key', 'groq_key_last4')
    op.drop_column('user_llm_key', 'groq_key_enc')
