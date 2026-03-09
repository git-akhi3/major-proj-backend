from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserOut(BaseModel):
    id: int
    github_id: int
    username: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
