from sqlalchemy import Column, Integer, BigInteger, String, DateTime
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(BigInteger, unique=True, nullable=False)
    pr_number = Column(Integer, nullable=False)
    repo_id = Column(BigInteger, nullable=False)
    reviewer = Column(String, nullable=True)
    state = Column(String, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
