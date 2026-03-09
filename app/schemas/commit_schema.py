from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CommitOut(BaseModel):
    id: int
    commit_sha: str
    repo_id: int
    author: Optional[str] = None
    message: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    commit_date: Optional[datetime] = None

    class Config:
        from_attributes = True
