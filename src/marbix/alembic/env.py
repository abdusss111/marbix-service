import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 1) Import your Base and all models so metadata is populated
from marbix.db.base import Base
import marbix.models.user  # add any additional model modules here
import marbix.models.make_request  # add any additional model modules here
# 2) Alembic Config object, provides access to values from alembic.ini
config = context.config

# 3) Override sqlalchemy.url with DATABASE_URL env var or -x argument
db_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
config.set_main_option("sqlalchemy.url", db_url)

# 4) Configure Python logging per alembic.ini
if config.config_file_name:
    fileConfig(config.config_file_name)

# 5) Supply your MetaData to Alembic for autogeneration
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode (no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode (with real DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # compare_type=True,  # uncomment to detect type changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
