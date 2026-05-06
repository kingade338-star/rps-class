from pydantic import BaseModel, EmailStr,Field
from datetime import datetime


class UserLogin(BaseModel):
    user_id: int
    email: str = Field( max_length= 100)


class GameHistoryResponse(BaseModel):
    id: int
    user_id: int
    user_choice: str
    computer_choice: str
    result: str
    played_at: datetime

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: str = Field( max_length= 100)
    username : str
    model_config = {"from_attributes": True}