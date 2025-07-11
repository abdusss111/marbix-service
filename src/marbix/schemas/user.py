# src/marbix/schemas/user.py

from pydantic import BaseModel, ConfigDict
from typing import Optional
class UserOut(BaseModel):
    id: str
    email: str
    name: str
    number: Optional[str] = None
    created_at: str
    model_config = ConfigDict(from_attributes=True)
