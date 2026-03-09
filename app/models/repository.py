from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime
from datetime import datetime, timezone
from app.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    private = Column(Boolean, default=False)
    language = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
