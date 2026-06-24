"""add model column to chat_message

Records which LLM produced each assistant message (e.g. "gemini/gemini-2.0-flash"), so the UI
can attribute replies. Nullable — user messages and pre-existing rows stay null.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chat_message',
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('chat_message', 'model')
