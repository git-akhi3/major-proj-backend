from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PullRequestOut(BaseModel):
    id: int
    pr_number: int
    repo_id: int
    author: Optional[str] = None
    state: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    created_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewOut(BaseModel):
    id: int
    review_id: int
    pr_number: int
    repo_id: int
    reviewer: Optional[str] = None
    state: Optional[str] = None
    submitted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
