from sqlalchemy.orm import Session
from app.models.commit import Commit
from app.models.pull_request import PullRequest
from app.models.review import Review


def get_commits_by_repo(db: Session, repo_id: int) -> list[Commit]:
    return db.query(Commit).filter(Commit.repo_id == repo_id).all()


def get_pull_requests_by_repo(db: Session, repo_id: int) -> list[PullRequest]:
    return db.query(PullRequest).filter(PullRequest.repo_id == repo_id).all()


def get_reviews_by_repo(db: Session, repo_id: int) -> list[Review]:
    return db.query(Review).filter(Review.repo_id == repo_id).all()
