import httpx
from typing import Optional
from datetime import datetime, timezone


GITHUB_API = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


async def get_authenticated_user(token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{GITHUB_API}/user", headers=_headers(token))
        resp.raise_for_status()
        return resp.json()


async def get_user_repos(token: str) -> list[dict]:
    """Fetch all repos for the authenticated user (including org repos)."""
    repos = []
    page = 1
    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(
                f"{GITHUB_API}/user/repos",
                headers=_headers(token),
                params={"per_page": 100, "page": page, "type": "all"},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            repos.extend(data)
            page += 1
    return repos


async def get_commits(owner: str, repo: str, token: str) -> list[dict]:
    """Fetch commits for a repository."""
    commits = []
    page = 1
    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                headers=_headers(token),
                params={"per_page": 100, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            commits.extend(data)
            page += 1
    return commits


async def get_commit_detail(owner: str, repo: str, sha: str, token: str) -> dict:
    """Fetch single commit details (for additions/deletions)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}",
            headers=_headers(token),
        )
        resp.raise_for_status()
        return resp.json()


async def get_pull_requests(owner: str, repo: str, token: str) -> list[dict]:
    """Fetch all pull requests for a repository."""
    prs = []
    page = 1
    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=_headers(token),
                params={"state": "all", "per_page": 100, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            prs.extend(data)
            page += 1
    return prs


async def get_pull_request_detail(owner: str, repo: str, pr_number: int, token: str) -> dict:
    """Fetch single PR details (for additions/deletions)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=_headers(token),
        )
        resp.raise_for_status()
        return resp.json()


async def get_pr_reviews(owner: str, repo: str, pr_number: int, token: str) -> list[dict]:
    """Fetch reviews for a specific pull request."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            headers=_headers(token),
        )
        resp.raise_for_status()
        return resp.json()


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string from GitHub API."""
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
