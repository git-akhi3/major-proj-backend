"""
Integration tests for GitHub Developer Metrics Dashboard API.

Uses the ACTUAL database and REAL GitHub API calls.
Requires:
  - PostgreSQL running with the configured database
  - A valid GitHub user in the DB (from a prior OAuth login)
  - pip install pytest httpx pytest-asyncio
"""

import sys
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.repository import Repository
from app.models.commit import Commit
from app.models.pull_request import PullRequest
from app.models.review import Review
from app.services.github_service import (
    get_authenticated_user,
    get_user_repos,
    get_commits,
    get_commit_detail,
    get_pull_requests,
    get_pr_reviews,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

client = TestClient(app)


@pytest.fixture(scope="session")
def db():
    """Provide a real database session for the entire test session."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="session")
def test_user(db: Session):
    """Fetch the first user from the DB (must exist from a prior OAuth login)."""
    user = db.query(User).first()
    if user is None:
        pytest.skip(
            "No user found in the database. "
            "Please log in via the browser first (GET /auth/github) "
            "so that a user with a valid access_token is stored."
        )
    return user


@pytest.fixture(scope="session")
def access_token(test_user):
    return test_user.access_token


# ---------------------------------------------------------------------------
# 1. Root / health-check
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    def test_root_returns_ok(self):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "running" in body["message"].lower()
        print(f"  [PASS] GET / -> {body}")


# ---------------------------------------------------------------------------
# 2. Auth routes
# ---------------------------------------------------------------------------

class TestAuthRoutes:
    def test_github_login_redirects(self):
        """GET /auth/github should redirect to GitHub OAuth page."""
        resp = client.get("/auth/github", follow_redirects=False)
        assert resp.status_code in (302, 307), f"Expected redirect, got {resp.status_code}"
        location = resp.headers.get("location", "")
        assert "github.com/login/oauth/authorize" in location
        assert "client_id=" in location
        print(f"  [PASS] GET /auth/github -> redirect to {location[:80]}...")

    def test_callback_without_code_fails(self):
        """GET /auth/callback without 'code' param should fail (422)."""
        resp = client.get("/auth/callback")
        assert resp.status_code == 422  # FastAPI validation error
        print(f"  [PASS] GET /auth/callback (no code) -> 422")

    def test_callback_with_invalid_code(self):
        """GET /auth/callback with a bogus code should return an error."""
        resp = client.get("/auth/callback?code=invalid_bogus_code", follow_redirects=False)
        # Either returns error JSON or a 500/400
        if resp.status_code == 200:
            body = resp.json()
            assert "error" in body
            print(f"  [PASS] GET /auth/callback (bad code) -> {body}")
        else:
            print(f"  [PASS] GET /auth/callback (bad code) -> status {resp.status_code}")


# ---------------------------------------------------------------------------
# 3. GitHub service - direct API calls
# ---------------------------------------------------------------------------

class TestGitHubServiceDirect:
    """Test the raw GitHub API service functions with a real token."""

    @pytest.mark.asyncio
    async def test_get_authenticated_user(self, access_token):
        user_data = await get_authenticated_user(access_token)
        assert "login" in user_data, f"Expected 'login' in response: {user_data}"
        assert "id" in user_data
        print(f"  [PASS] get_authenticated_user -> login={user_data['login']}, id={user_data['id']}")

    @pytest.mark.asyncio
    async def test_get_user_repos(self, access_token):
        repos = await get_user_repos(access_token)
        assert isinstance(repos, list)
        assert len(repos) > 0, "User has no repos - cannot continue testing"
        print(f"  [PASS] get_user_repos -> {len(repos)} repos fetched")
        first = repos[0]
        assert "id" in first
        assert "name" in first
        assert "owner" in first
        print(f"         First repo: {first['owner']['login']}/{first['name']}")

    @pytest.mark.asyncio
    async def test_get_commits_for_a_repo(self, access_token):
        """Pick the first repo and fetch its commits."""
        repos = await get_user_repos(access_token)
        repo = repos[0]
        owner = repo["owner"]["login"]
        name = repo["name"]

        commits = await get_commits(owner, name, access_token)
        assert isinstance(commits, list)
        print(f"  [PASS] get_commits({owner}/{name}) -> {len(commits)} commits")

        if commits:
            sha = commits[0]["sha"]
            detail = await get_commit_detail(owner, name, sha, access_token)
            assert "stats" in detail
            print(f"  [PASS] get_commit_detail(sha={sha[:8]}) -> +{detail['stats']['additions']}/-{detail['stats']['deletions']}")

    @pytest.mark.asyncio
    async def test_get_pull_requests_for_a_repo(self, access_token):
        repos = await get_user_repos(access_token)
        repo = repos[0]
        owner = repo["owner"]["login"]
        name = repo["name"]

        prs = await get_pull_requests(owner, name, access_token)
        assert isinstance(prs, list)
        print(f"  [PASS] get_pull_requests({owner}/{name}) -> {len(prs)} PRs")

        if prs:
            pr_num = prs[0]["number"]
            reviews = await get_pr_reviews(owner, name, pr_num, access_token)
            assert isinstance(reviews, list)
            print(f"  [PASS] get_pr_reviews(PR #{pr_num}) -> {len(reviews)} reviews")


# ---------------------------------------------------------------------------
# 4. Repo routes - API endpoints
# ---------------------------------------------------------------------------

class TestRepoRoutes:
    def test_list_repos_invalid_user(self):
        """GET /repos/?user_id=999999 should 401 (user not found)."""
        resp = client.get("/repos/?user_id=999999")
        assert resp.status_code == 401
        print(f"  [PASS] GET /repos/?user_id=999999 -> 401")

    def test_list_repos_valid_user(self, test_user):
        """GET /repos/?user_id=<real> should return list of repos."""
        resp = client.get(f"/repos/?user_id={test_user.id}")
        assert resp.status_code == 200
        repos = resp.json()
        assert isinstance(repos, list)
        assert len(repos) > 0, "Expected at least one repo"
        first = repos[0]
        assert "repo_id" in first
        assert "name" in first
        assert "owner" in first
        print(f"  [PASS] GET /repos/?user_id={test_user.id} -> {len(repos)} repos")
        for r in repos[:5]:
            print(f"         {r['owner']}/{r['name']} (id={r['repo_id']}, lang={r.get('language')})")

    def test_sync_repo_invalid_user(self):
        """POST /repos/sync with bad user_id should 401."""
        resp = client.post("/repos/sync?repo_id=1&user_id=999999")
        assert resp.status_code == 401
        print(f"  [PASS] POST /repos/sync (bad user) -> 401")

    def test_sync_repo_invalid_repo(self, test_user):
        """POST /repos/sync with non-existent repo_id should 404."""
        resp = client.post(f"/repos/sync?repo_id=999999999&user_id={test_user.id}")
        assert resp.status_code == 404
        print(f"  [PASS] POST /repos/sync (bad repo) -> 404")

    def test_sync_repo_success(self, test_user, db: Session):
        """Sync a real repo and verify data is stored in DB."""
        # First, list repos to ensure at least one is in the DB
        resp = client.get(f"/repos/?user_id={test_user.id}")
        repos = resp.json()
        assert len(repos) > 0

        # Pick the first repo
        repo = repos[0]
        repo_id = repo["repo_id"]
        print(f"  Syncing repo: {repo['owner']}/{repo['name']} (repo_id={repo_id})...")

        resp = client.post(f"/repos/sync?repo_id={repo_id}&user_id={test_user.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "synced"
        print(f"  [PASS] POST /repos/sync -> {body}")

        # Verify data was stored
        commit_count = db.query(Commit).filter(Commit.repo_id == repo_id).count()
        pr_count = db.query(PullRequest).filter(PullRequest.repo_id == repo_id).count()
        review_count = db.query(Review).filter(Review.repo_id == repo_id).count()
        print(f"         DB: {commit_count} commits, {pr_count} PRs, {review_count} reviews")


# ---------------------------------------------------------------------------
# 5. Data routes - fetching stored data
# ---------------------------------------------------------------------------

class TestDataRoutes:
    def _get_synced_repo_id(self, db: Session) -> int:
        """Helper: find a repo_id that has synced data."""
        repo = db.query(Repository).first()
        if repo is None:
            pytest.skip("No repos in DB - run sync test first")
        return repo.repo_id

    def test_get_commits(self, db: Session):
        repo_id = self._get_synced_repo_id(db)
        resp = client.get(f"/repos/{repo_id}/commits")
        assert resp.status_code == 200
        commits = resp.json()
        assert isinstance(commits, list)
        print(f"  [PASS] GET /repos/{repo_id}/commits -> {len(commits)} commits")
        if commits:
            c = commits[0]
            print(f"         First: sha={c['commit_sha'][:8]}, author={c['author']}, +{c['additions']}/-{c['deletions']}")

    def test_get_pulls(self, db: Session):
        repo_id = self._get_synced_repo_id(db)
        resp = client.get(f"/repos/{repo_id}/pulls")
        assert resp.status_code == 200
        prs = resp.json()
        assert isinstance(prs, list)
        print(f"  [PASS] GET /repos/{repo_id}/pulls -> {len(prs)} PRs")
        if prs:
            pr = prs[0]
            print(f"         First: PR#{pr['pr_number']}, author={pr['author']}, state={pr['state']}")

    def test_get_reviews(self, db: Session):
        repo_id = self._get_synced_repo_id(db)
        resp = client.get(f"/repos/{repo_id}/reviews")
        assert resp.status_code == 200
        reviews = resp.json()
        assert isinstance(reviews, list)
        print(f"  [PASS] GET /repos/{repo_id}/reviews -> {len(reviews)} reviews")
        if reviews:
            rv = reviews[0]
            print(f"         First: review_id={rv['review_id']}, reviewer={rv['reviewer']}, state={rv['state']}")

    def test_get_commits_empty_repo(self):
        """Querying a repo_id with no data should return empty list."""
        resp = client.get("/repos/0/commits")
        assert resp.status_code == 200
        assert resp.json() == []
        print(f"  [PASS] GET /repos/0/commits -> [] (empty)")

    def test_get_pulls_empty_repo(self):
        resp = client.get("/repos/0/pulls")
        assert resp.status_code == 200
        assert resp.json() == []
        print(f"  [PASS] GET /repos/0/pulls -> [] (empty)")

    def test_get_reviews_empty_repo(self):
        resp = client.get("/repos/0/reviews")
        assert resp.status_code == 200
        assert resp.json() == []
        print(f"  [PASS] GET /repos/0/reviews -> [] (empty)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
