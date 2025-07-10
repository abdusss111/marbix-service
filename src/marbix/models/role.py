import enum
from sqlalchemy import Enum

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
