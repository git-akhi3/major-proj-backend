"""
Integration tests for all API endpoints.
Uses the real database and real GitHub API calls.
Run with: python -m pytest tests/test_api_integration.py -v -s
"""

import asyncio
import httpx
import pytest
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
    get_pull_request_detail,
    get_pr_reviews,
)
from app.services.repo_service import sync_repository_data
from app.services.metrics_service import (
    get_commits_by_repo,
    get_pull_requests_by_repo,
    get_reviews_by_repo,
)

BASE_URL = "http://localhost:8000"


def run_async(coro):
    """Helper to run an async coroutine from sync test code."""
    return asyncio.run(coro)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def user(db):
    u = db.query(User).first()
    assert u is not None, "No user in database. Log in via /auth/github first."
    return u


@pytest.fixture(scope="module")
def token(user):
    return user.access_token


@pytest.fixture(scope="module")
def repo(db):
    r = db.query(Repository).first()
    assert r is not None, "No repository in database. Call GET /repos/?user_id=1 first."
    return r


# ── 1. GitHub Service Layer Tests (real API) ──────────────────────────────

class TestGitHubService:
    """Test the raw GitHub API wrappers with real credentials."""

    def test_get_authenticated_user(self, token):
        result = run_async(get_authenticated_user(token))
        assert "login" in result
        assert "id" in result
        print(f"  ✓ Authenticated as: {result['login']} (id={result['id']})")

    def test_get_user_repos(self, token):
        repos = run_async(get_user_repos(token))
        assert isinstance(repos, list)
        assert len(repos) > 0
        first = repos[0]
        assert "id" in first
        assert "name" in first
        assert "owner" in first
        print(f"  ✓ Found {len(repos)} repositories")

    def test_get_commits(self, token, repo):
        commits = run_async(get_commits(repo.owner, repo.name, token))
        assert isinstance(commits, list)
        print(f"  ✓ Repo '{repo.name}' has {len(commits)} commits")
        if commits:
            c = commits[0]
            assert "sha" in c
            assert "commit" in c

    def test_get_commit_detail(self, token, repo):
        commits = run_async(get_commits(repo.owner, repo.name, token))
        if not commits:
            pytest.skip("No commits to test detail on")
        sha = commits[0]["sha"]
        detail = run_async(get_commit_detail(repo.owner, repo.name, sha, token))
        assert "stats" in detail
        assert "additions" in detail["stats"]
        assert "deletions" in detail["stats"]
        print(f"  ✓ Commit {sha[:8]} — +{detail['stats']['additions']}/-{detail['stats']['deletions']}")

    def test_get_pull_requests(self, token, repo):
        prs = run_async(get_pull_requests(repo.owner, repo.name, token))
        assert isinstance(prs, list)
        print(f"  ✓ Repo '{repo.name}' has {len(prs)} pull requests")
        if prs:
            assert "number" in prs[0]
            assert "state" in prs[0]

    def test_get_pull_request_detail(self, token, repo):
        prs = run_async(get_pull_requests(repo.owner, repo.name, token))
        if not prs:
            pytest.skip("No PRs to test detail on")
        pr_num = prs[0]["number"]
        detail = run_async(get_pull_request_detail(repo.owner, repo.name, pr_num, token))
        assert "additions" in detail
        assert "deletions" in detail
        print(f"  ✓ PR #{pr_num} — +{detail['additions']}/-{detail['deletions']}")

    def test_get_pr_reviews(self, token, repo):
        prs = run_async(get_pull_requests(repo.owner, repo.name, token))
        if not prs:
            pytest.skip("No PRs to test reviews on")
        pr_num = prs[0]["number"]
        reviews = run_async(get_pr_reviews(repo.owner, repo.name, pr_num, token))
        assert isinstance(reviews, list)
        print(f"  ✓ PR #{pr_num} has {len(reviews)} reviews")


# ── 2. Repo Service Layer Tests ──────────────────────────────────────────

class TestRepoService:
    """Test the sync_repository_data service with real GitHub data."""

    def test_sync_repository_data(self, db, repo, token):
        run_async(sync_repository_data(db, repo, token))
        commits = db.query(Commit).filter(Commit.repo_id == repo.repo_id).count()
        prs = db.query(PullRequest).filter(PullRequest.repo_id == repo.repo_id).count()
        reviews = db.query(Review).filter(Review.repo_id == repo.repo_id).count()
        print(f"  ✓ Synced repo '{repo.name}': {commits} commits, {prs} PRs, {reviews} reviews")
        assert commits >= 0
        assert prs >= 0
        assert reviews >= 0

    def test_sync_idempotent(self, db, repo, token):
        """Running sync twice should not create duplicates."""
        before_commits = db.query(Commit).filter(Commit.repo_id == repo.repo_id).count()
        before_prs = db.query(PullRequest).filter(PullRequest.repo_id == repo.repo_id).count()
        before_reviews = db.query(Review).filter(Review.repo_id == repo.repo_id).count()

        run_async(sync_repository_data(db, repo, token))

        after_commits = db.query(Commit).filter(Commit.repo_id == repo.repo_id).count()
        after_prs = db.query(PullRequest).filter(PullRequest.repo_id == repo.repo_id).count()
        after_reviews = db.query(Review).filter(Review.repo_id == repo.repo_id).count()

        assert after_commits == before_commits, f"Commit duplicates: {before_commits} → {after_commits}"
        assert after_prs == before_prs, f"PR duplicates: {before_prs} → {after_prs}"
        assert after_reviews == before_reviews, f"Review duplicates: {before_reviews} → {after_reviews}"
        print(f"  ✓ Idempotent: still {after_commits} commits, {after_prs} PRs, {after_reviews} reviews")


# ── 3. Metrics Service Layer Tests ───────────────────────────────────────

class TestMetricsService:
    """Test the metrics/data retrieval service layer."""

    def test_get_commits_by_repo(self, db, repo):
        commits = get_commits_by_repo(db, repo.repo_id)
        assert isinstance(commits, list)
        print(f"  ✓ get_commits_by_repo returned {len(commits)} commits")
        if commits:
            c = commits[0]
            assert c.commit_sha is not None
            assert c.repo_id == repo.repo_id

    def test_get_pull_requests_by_repo(self, db, repo):
        prs = get_pull_requests_by_repo(db, repo.repo_id)
        assert isinstance(prs, list)
        print(f"  ✓ get_pull_requests_by_repo returned {len(prs)} PRs")
        if prs:
            pr = prs[0]
            assert pr.pr_number is not None
            assert pr.repo_id == repo.repo_id

    def test_get_reviews_by_repo(self, db, repo):
        reviews = get_reviews_by_repo(db, repo.repo_id)
        assert isinstance(reviews, list)
        print(f"  ✓ get_reviews_by_repo returned {len(reviews)} reviews")
        if reviews:
            r = reviews[0]
            assert r.review_id is not None
            assert r.repo_id == repo.repo_id


# ── 4. HTTP API Endpoint Tests (requires running server) ─────────────────

class TestHTTPEndpoints:
    """Test actual HTTP endpoints against the running server."""

    @pytest.fixture(autouse=True)
    def _check_server(self):
        """Skip all HTTP tests if server is not running."""
        try:
            r = httpx.get(f"{BASE_URL}/", timeout=5)
            if r.status_code != 200:
                pytest.skip("Server not responding correctly")
        except httpx.ConnectError:
            pytest.skip("Server not running at localhost:8000")

    def test_root(self):
        r = httpx.get(f"{BASE_URL}/")
        assert r.status_code == 200
        data = r.json()
        assert "message" in data
        print(f"  ✓ GET / => {data}")

    def test_list_repos(self, user):
        r = httpx.get(f"{BASE_URL}/repos/", params={"user_id": user.id}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        first = data[0]
        assert "repo_id" in first
        assert "name" in first
        assert "owner" in first
        print(f"  ✓ GET /repos/ => {len(data)} repos returned")

    def test_sync_repo(self, user, repo):
        r = httpx.post(
            f"{BASE_URL}/repos/sync",
            params={"repo_id": repo.repo_id, "user_id": user.id},
            timeout=120,
        )
        assert r.status_code == 200, f"Sync failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["status"] == "synced"
        assert data["repo"] == repo.name
        print(f"  ✓ POST /repos/sync => {data}")

    def test_get_commits_endpoint(self, repo):
        r = httpx.get(f"{BASE_URL}/repos/{repo.repo_id}/commits", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        print(f"  ✓ GET /repos/{repo.repo_id}/commits => {len(data)} commits")
        if data:
            c = data[0]
            assert "commit_sha" in c
            assert "author" in c
            assert "additions" in c

    def test_get_pulls_endpoint(self, repo):
        r = httpx.get(f"{BASE_URL}/repos/{repo.repo_id}/pulls", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        print(f"  ✓ GET /repos/{repo.repo_id}/pulls => {len(data)} PRs")
        if data:
            pr = data[0]
            assert "pr_number" in pr
            assert "author" in pr
            assert "state" in pr

    def test_get_reviews_endpoint(self, repo):
        r = httpx.get(f"{BASE_URL}/repos/{repo.repo_id}/reviews", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        print(f"  ✓ GET /repos/{repo.repo_id}/reviews => {len(data)} reviews")
        if data:
            rv = data[0]
            assert "review_id" in rv
            assert "reviewer" in rv
            assert "state" in rv

    def test_sync_nonexistent_repo(self, user):
        r = httpx.post(
            f"{BASE_URL}/repos/sync",
            params={"repo_id": 999999999, "user_id": user.id},
            timeout=10,
        )
        assert r.status_code == 404
        print(f"  ✓ Sync non-existent repo => 404 (correct)")

    def test_sync_nonexistent_user(self, repo):
        r = httpx.post(
            f"{BASE_URL}/repos/sync",
            params={"repo_id": repo.repo_id, "user_id": 9999},
            timeout=10,
        )
        assert r.status_code == 401
        print(f"  ✓ Sync non-existent user => 401 (correct)")

    def test_list_repos_nonexistent_user(self):
        r = httpx.get(f"{BASE_URL}/repos/", params={"user_id": 9999}, timeout=10)
        assert r.status_code == 401
        print(f"  ✓ List repos non-existent user => 401 (correct)")

    def test_auth_github_redirect(self):
        r = httpx.get(f"{BASE_URL}/auth/github", follow_redirects=False, timeout=10)
        assert r.status_code in (302, 307)
        location = r.headers.get("location", "")
        assert "github.com/login/oauth/authorize" in location
        print(f"  ✓ GET /auth/github => redirect to GitHub OAuth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
