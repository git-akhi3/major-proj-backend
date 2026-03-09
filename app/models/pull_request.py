from sqlalchemy import Column, Integer, BigInteger, String, DateTime, UniqueConstraint
from app.database import Base


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("pr_number", "repo_id", name="uq_pr_repo"),)

    id = Column(Integer, primary_key=True, index=True)
    pr_number = Column(Integer, nullable=False)
    repo_id = Column(BigInteger, nullable=False)
    author = Column(String, nullable=True)
    state = Column(String, nullable=True)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=True)
    merged_at = Column(DateTime, nullable=True)
