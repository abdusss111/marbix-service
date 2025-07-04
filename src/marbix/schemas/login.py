from pydantic import BaseModel
from typing import Literal
from .user import UserOut  
class LoginRequest(BaseModel):
    code: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int             # seconds until expiry
