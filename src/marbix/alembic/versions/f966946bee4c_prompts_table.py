"""prompts table

Revision ID: f966946bee4c
Revises: 
Create Date: 2025-08-12 15:12:23.710534

Creates the 'prompts' table used by the prompt management system.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f966946bee4c'
# If your project already has previous migrations, set this to the latest
# previous revision hash instead of None so this migration chains correctly.
# For first-time setup, keeping None is acceptable.
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create prompts table and indexes."""
    op.create_table(
        'prompts',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(), nullable=True, index=True),
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

    # Additional indexes
    op.create_index('ix_prompts_name', 'prompts', ['name'], unique=False)
    op.create_index('ix_prompts_category', 'prompts', ['category'], unique=False)
    op.create_index('ix_prompts_created_by', 'prompts', ['created_by'], unique=False)
    op.create_index('ix_prompts_parent_id', 'prompts', ['parent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema: drop prompts table and indexes."""
    op.drop_index('ix_prompts_parent_id', table_name='prompts')
    op.drop_index('ix_prompts_created_by', table_name='prompts')
    op.drop_index('ix_prompts_category', table_name='prompts')
    op.drop_index('ix_prompts_name', table_name='prompts')
    op.drop_table('prompts')
