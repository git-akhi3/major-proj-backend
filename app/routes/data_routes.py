from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.commit_schema import CommitOut
from app.schemas.pr_schema import PullRequestOut, ReviewOut
from app.services.metrics_service import (
    get_commits_by_repo,
    get_pull_requests_by_repo,
    get_reviews_by_repo,
)

router = APIRouter(tags=["data"])


@router.get("/repos/{repo_id}/commits", response_model=list[CommitOut])
def get_commits(repo_id: int, db: Session = Depends(get_db)):
    return get_commits_by_repo(db, repo_id)


@router.get("/repos/{repo_id}/pulls", response_model=list[PullRequestOut])
def get_pulls(repo_id: int, db: Session = Depends(get_db)):
    return get_pull_requests_by_repo(db, repo_id)


@router.get("/repos/{repo_id}/reviews", response_model=list[ReviewOut])
def get_reviews(repo_id: int, db: Session = Depends(get_db)):
    return get_reviews_by_repo(db, repo_id)
