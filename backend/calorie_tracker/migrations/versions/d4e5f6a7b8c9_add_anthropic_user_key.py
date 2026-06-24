"""add anthropic key columns to user_llm_key

Lets users store a personal Anthropic (Claude) key alongside their Gemini one. Both nullable.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_llm_key',
        sa.Column('anthropic_key_enc', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
    )
    op.add_column(
        'user_llm_key',
        sa.Column('anthropic_key_last4', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('user_llm_key', 'anthropic_key_last4')
    op.drop_column('user_llm_key', 'anthropic_key_enc')
