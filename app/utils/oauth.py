import httpx
from app.config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET


async def exchange_code_for_token(code: str) -> str:
    """Exchange the OAuth callback code for an access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        data = response.json()
        return data.get("access_token")
