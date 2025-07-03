from sqlalchemy.orm import Session
from marbix.models.user import User


def get_user_by_id(db: Session, user_id: str) -> User | None:
    """
    Fetch a user by their unique ID.

    :param db: SQLAlchemy Session
    :param user_id: The user's unique identifier
    :return: User instance or None if not found
    """
    return db.query(User).filter(User.id == user_id).first()
