"""f

Revision ID: 50235e2bd293
Revises: d34a3027b645
Create Date: 2025-07-22 01:15:17.056363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '50235e2bd293'
down_revision: Union[str, Sequence[str], None] = 'd34a3027b645'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1) Add 'sources' column to make_requests
    op.add_column(
        'make_requests',
        sa.Column('sources', sa.Text(), nullable=True),
    )

    # 2) Create the PostgreSQL ENUM type before altering users.role
    userrole = postgresql.ENUM('ADMIN', 'USER', name='userrole')
    userrole.create(op.get_bind(), checkfirst=True)

    # 3) Alter other users columns
    op.alter_column(
        'users', 'id',
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.alter_column(
        'users', 'email',
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.alter_column(
        'users', 'name',
        existing_type=sa.TEXT(),
        type_=sa.String(),
        nullable=True,
    )
    op.alter_column(
        'users', 'number',
        existing_type=sa.VARCHAR(),
        nullable=False,
    )

    # 4) Alter users.role to use the new ENUM, with USING to cast existing values
    op.alter_column(
        'users', 'role',
        existing_type=sa.VARCHAR(),
        type_=sa.Enum('ADMIN', 'USER', name='userrole'),
        existing_nullable=False,
        existing_server_default=sa.text("'user'::character varying"),
        postgresql_using="role::userrole",
    )

    op.alter_column(
        'users', 'created_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
        existing_server_default=sa.text('CURRENT_TIMESTAMP'),
    )

    # 5) Swap out the old unique constraint on email for a unique index
    op.drop_constraint(op.f('users_email_key'), 'users', type_='unique')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    # 1) Drop the newly created indexes
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')

    # 2) Restore the unique constraint on email
    op.create_unique_constraint(op.f('users_email_key'), 'users', ['email'])

    # 3) Revert users.created_at
    op.alter_column(
        'users', 'created_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
        existing_server_default=sa.text('CURRENT_TIMESTAMP'),
    )

    # 4) Revert users.role back to plain VARCHAR
    op.alter_column(
        'users', 'role',
        existing_type=sa.Enum('ADMIN', 'USER', name='userrole'),
        type_=sa.VARCHAR(),
        existing_nullable=False,
        existing_server_default=sa.text("'user'::character varying"),
    )

    # 5) Revert other users columns
    op.alter_column(
        'users', 'number',
        existing_type=sa.VARCHAR(),
        nullable=True,
    )
    op.alter_column(
        'users', 'name',
        existing_type=sa.String(),
        type_=sa.TEXT(),
        nullable=False,
    )
    op.alter_column(
        'users', 'email',
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )
    op.alter_column(
        'users', 'id',
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )

    # 6) Drop the 'sources' column on make_requests
    op.drop_column('make_requests', 'sources')

    # 7) Finally drop the ENUM type
    userrole = postgresql.ENUM('ADMIN', 'USER', name='userrole')
    userrole.drop(op.get_bind(), checkfirst=True)

