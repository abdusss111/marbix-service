# src/marbix/db/base.py
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Note: Models are imported elsewhere to avoid circular imports
# All models inherit from this Base class