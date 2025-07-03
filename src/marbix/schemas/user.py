from pydantic import BaseModel

class UserOut(BaseModel):
    name: str
    email: str

    class Config:
        orm_mode = True

