from sqlalchemy import Column, Integer, BigInteger, String, DateTime
from app.database import Base


class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    commit_sha = Column(String, unique=True, nullable=False)
    repo_id = Column(BigInteger, nullable=False)
    author = Column(String, nullable=True)
    message = Column(String, nullable=True)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    commit_date = Column(DateTime, nullable=True)
