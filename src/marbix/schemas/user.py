# src/marbix/schemas/user.py

from pydantic import BaseModel, ConfigDict

class UserOut(BaseModel):
    id: str
    email: str
    name: str

    # Pydantic v2: allow .from_orm() on SQLAlchemy models
    model_config = ConfigDict(from_attributes=True)
