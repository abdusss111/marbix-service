"""create prompts table (fix)

Revision ID: 2f1db3c7a9a1
Revises: f966946bee4c
Create Date: 2025-08-12 16:05:00.000000

This migration actually creates the 'prompts' table in case the previous
revision was applied without creating it.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f1db3c7a9a1'
down_revision: Union[str, Sequence[str], None] = 'f966946bee4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create prompts table and indexes if they don't exist."""
    # Create table only if not exists (PostgreSQL doesn't support IF NOT EXISTS for CREATE TABLE
    # via Alembic Op, so we guard by checking information_schema using raw SQL)
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        """
        SELECT to_regclass('public.prompts') IS NOT NULL AS exists
        """
    )).scalar()

    if not exists:
        op.create_table(
            'prompts',
            sa.Column('id', sa.String(), primary_key=True, nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('category', sa.String(), nullable=True),
            sa.Column('tags', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('parent_id', sa.String(), nullable=True),
            sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        )

        op.create_index('ix_prompts_name', 'prompts', ['name'], unique=False)
        op.create_index('ix_prompts_category', 'prompts', ['category'], unique=False)
        op.create_index('ix_prompts_created_by', 'prompts', ['created_by'], unique=False)
        op.create_index('ix_prompts_parent_id', 'prompts', ['parent_id'], unique=False)


def downgrade() -> None:
    """Drop prompts table and indexes if they exist."""
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        """
        SELECT to_regclass('public.prompts') IS NOT NULL AS exists
        """
    )).scalar()

    if exists:
        op.drop_index('ix_prompts_parent_id', table_name='prompts')
        op.drop_index('ix_prompts_created_by', table_name='prompts')
        op.drop_index('ix_prompts_category', table_name='prompts')
        op.drop_index('ix_prompts_name', table_name='prompts')
        op.drop_table('prompts')


