# src/marbix/schemas/user.py

from pydantic import BaseModel, ConfigDict

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
