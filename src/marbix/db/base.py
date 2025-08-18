# src/marbix/db/base.py
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models to ensure they are registered with SQLAlchemy
from marbix.models.user import User
from marbix.models.role import UserRole  
from marbix.models.make_request import MakeRequest
from marbix.models.prompt import Prompt
from marbix.models.enhanced_strategy import EnhancedStrategy