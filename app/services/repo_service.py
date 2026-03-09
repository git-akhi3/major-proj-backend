from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.commit import Commit
from app.models.pull_request import PullRequest
from app.models.review import Review
from app.services.github_service import (
    get_commits,
    get_commit_detail,
    get_pull_requests,
    get_pull_request_detail,
    get_pr_reviews,
    parse_datetime,
)


async def sync_repository_data(db: Session, repo: Repository, token: str):
    """Fetch commits, PRs, and reviews from GitHub and store them."""
    owner = repo.owner
    name = repo.name

    # Sync commits
    raw_commits = await get_commits(owner, name, token)
    for c in raw_commits:
        sha = c["sha"]
        existing = db.query(Commit).filter(Commit.commit_sha == sha).first()
        if existing:
            continue

        # Fetch detailed commit info for additions/deletions
        detail = await get_commit_detail(owner, name, sha, token)
        stats = detail.get("stats", {})

        # Use GitHub login if available, fall back to Git commit author name
        author_login = (c.get("author") or {}).get("login")
        author_name = c.get("commit", {}).get("author", {}).get("name")

        commit = Commit(
            commit_sha=sha,
            repo_id=repo.repo_id,
            author=author_login or author_name,
            message=c.get("commit", {}).get("message", "")[:500],
            additions=stats.get("additions", 0),
            deletions=stats.get("deletions", 0),
            commit_date=parse_datetime(
                c.get("commit", {}).get("author", {}).get("date")
            ),
        )
        db.add(commit)
    db.commit()

    # Sync pull requests
    raw_prs = await get_pull_requests(owner, name, token)
    for pr in raw_prs:
        pr_num = pr["number"]
        existing = db.query(PullRequest).filter(
            PullRequest.pr_number == pr_num,
            PullRequest.repo_id == repo.repo_id,
        ).first()
        if existing:
            continue

        # Fetch detailed PR info for additions/deletions
        pr_detail = await get_pull_request_detail(owner, name, pr_num, token)

        pull = PullRequest(
            pr_number=pr_num,
            repo_id=repo.repo_id,
            author=pr.get("user", {}).get("login"),
            state=pr.get("state"),
            additions=pr_detail.get("additions", 0),
            deletions=pr_detail.get("deletions", 0),
            created_at=parse_datetime(pr.get("created_at")),
            merged_at=parse_datetime(pr.get("merged_at")),
        )
        db.add(pull)
    db.commit()

    # Sync reviews
    for pr in raw_prs:
        pr_num = pr["number"]
        raw_reviews = await get_pr_reviews(owner, name, pr_num, token)
        for rv in raw_reviews:
            rev_id = rv["id"]
            existing = db.query(Review).filter(Review.review_id == rev_id).first()
            if existing:
                continue

            review = Review(
                review_id=rev_id,
                pr_number=pr_num,
                repo_id=repo.repo_id,
                reviewer=rv.get("user", {}).get("login"),
                state=rv.get("state"),
                submitted_at=parse_datetime(rv.get("submitted_at")),
            )
            db.add(review)
    db.commit()
