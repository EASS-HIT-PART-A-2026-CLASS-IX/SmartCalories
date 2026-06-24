"""drop unused api_key table

The api_key table was created for a planned personal-API-key / MCP feature that was descoped.
No SQLModel model or code references it, so this migration drops the orphan table.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_api_key_user_uid'), table_name='api_key')
    op.drop_index(op.f('ix_api_key_prefix'), table_name='api_key')
    op.drop_table('api_key')


def downgrade() -> None:
    # Recreate the table exactly as e17fc69f1b15 created it.
    op.create_table(
        'api_key',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_uid', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column('prefix', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
        sa.Column('key_hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_uid'], ['user.uid'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_api_key_prefix'), 'api_key', ['prefix'], unique=False)
    op.create_index(op.f('ix_api_key_user_uid'), 'api_key', ['user_uid'], unique=False)
