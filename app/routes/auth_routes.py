from urllib.parse import urlencode
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db
from app.config import GITHUB_CLIENT_ID, GITHUB_REDIRECT_URI, FRONTEND_URL
from app.utils.oauth import exchange_code_for_token
from app.services.github_service import get_authenticated_user
from app.models.user import User
from app.schemas.user_schema import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Return public profile info for a user (no access token exposed)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/github")
async def github_login():
    """Redirect user to GitHub OAuth authorization page."""
    params = urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "repo read:org",
    })
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.get("/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback: exchange code, store user, redirect."""
    access_token = await exchange_code_for_token(code)
    if not access_token:
        return {"error": "Failed to get access token"}

    github_user = await get_authenticated_user(access_token)

    # Upsert user
    user = db.query(User).filter(User.github_id == github_user["id"]).first()
    if user:
        user.access_token = access_token
        user.username = github_user["login"]
    else:
        user = User(
            github_id=github_user["id"],
            username=github_user["login"],
            access_token=access_token,
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    # Redirect to frontend repo selector with user id
    return RedirectResponse(f"{FRONTEND_URL}/repos?user_id={user.id}")
