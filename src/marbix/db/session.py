import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from marbix.core.config import settings


# Engine and session factory
engine = create_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True
)