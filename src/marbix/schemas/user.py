from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional
class UserOut(BaseModel):
    id: str
    email: str
    name: str
    number: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
