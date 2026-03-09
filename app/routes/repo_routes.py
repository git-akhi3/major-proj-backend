from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import httpx
import logging
from app.database import get_db
from app.models.user import User
from app.models.repository import Repository
from app.schemas.repo_schema import RepoOut
from app.services.github_service import get_user_repos
from app.services.repo_service import sync_repository_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repos", tags=["repos"])


def _get_user(user_id: int, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/", response_model=list[RepoOut])
async def list_repos(user_id: int = Query(...), db: Session = Depends(get_db)):
    """Fetch repos from GitHub and return them (also stores in DB)."""
    user = _get_user(user_id, db)
    try:
        github_repos = await get_user_repos(user.access_token)
    except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.error(f"GitHub API error fetching repos: {e}")
        raise HTTPException(status_code=502, detail="GitHub API is temporarily unavailable. Please try again.")

    repos = []
    for r in github_repos:
        existing = db.query(Repository).filter(Repository.repo_id == r["id"]).first()
        if not existing:
            existing = Repository(
                repo_id=r["id"],
                name=r["name"],
                owner=r["owner"]["login"],
                private=r["private"],
                language=r.get("language"),
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)
        repos.append(existing)

    return repos


@router.post("/sync")
async def sync_repo(
    repo_id: int = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Sync commits, PRs, and reviews for a selected repository."""
    user = _get_user(user_id, db)
    repo = db.query(Repository).filter(Repository.repo_id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        await sync_repository_data(db, repo, user.access_token)
    except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.error(f"GitHub API error syncing repo {repo.name}: {e}")
        raise HTTPException(status_code=502, detail="GitHub API timed out during sync. Please try again.")
    return {"status": "synced", "repo": repo.name}
