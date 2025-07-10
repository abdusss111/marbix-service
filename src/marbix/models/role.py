import enum
from sqlalchemy import Enum

class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"
