from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RepoOut(BaseModel):
    id: int
    repo_id: int
    name: str
    owner: str
    private: bool
    language: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
