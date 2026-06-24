"""add user_llm_key table

Revision ID: a1b2c3d4e5f6
Revises: e17fc69f1b15
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e17fc69f1b15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_llm_key',
        sa.Column('user_uid', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('gemini_key_enc', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column('gemini_key_last4', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_uid'], ['user.uid'], ),
        sa.PrimaryKeyConstraint('user_uid'),
    )


def downgrade() -> None:
    op.drop_table('user_llm_key')
