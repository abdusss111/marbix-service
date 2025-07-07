from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base
from marbix.models.user import User
from marbix.models.make_request import MakeRequest  # Добавьте эту строку
# Naming convention ensures consistent names for constraints/indexes,
# which is especially useful for Alembic autogeneration.
naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=naming_convention)

# Base class for all ORM models
Base = declarative_base(metadata=metadata)
