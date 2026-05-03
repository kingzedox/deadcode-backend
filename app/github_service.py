"""
DeadCode — GitHub Service
Fetches the file tree and individual file contents from a public GitHub repo
using the REST API (no authentication required for public repos).
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("deadcode.github")


@dataclass
class RepoFile:
    """Lightweight container for a fetched source file."""

    path: str
    content: str
    size: int


def parse_owner_repo(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL."""
    parts = repo_url.rstrip("/").split("/")
    return parts[-2], parts[-1]


async def fetch_repo_tree(owner: str, repo: str) -> list[dict]:
    """
    Use the Git Trees API (recursive) to get every file path in one call.
    Falls back to the Contents API if the tree is too large.
    """
    url = f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {settings.GITHUB_TOKEN}"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Filter to blobs (files) only
    return [
        item
        for item in data.get("tree", [])
        if item.get("type") == "blob"
    ]


def _should_include(path: str, size: int | None) -> bool:
    """Decide whether a file is worth fetching based on extension and size."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in settings.SUPPORTED_EXTENSIONS:
        return False
    if size and size > settings.MAX_FILE_SIZE_BYTES:
        return False
    # Skip common non-app files
    skip_dirs = {"node_modules", "vendor", "dist", "build", ".next", "__pycache__", ".git"}
    if any(part in skip_dirs for part in path.split("/")):
        return False
    return True


async def fetch_file_contents(
    owner: str,
    repo: str,
    tree: list[dict],
) -> list[RepoFile]:
    """
    Download the raw contents of each relevant file in the tree.
    Uses the Contents API which returns base64-encoded content.
    Caps total files at MAX_FILES_TO_FETCH.
    """
    # Filter and cap
    candidates = [f for f in tree if _should_include(f["path"], f.get("size"))]
    candidates = candidates[: settings.MAX_FILES_TO_FETCH]

    logger.info("Fetching %d / %d files from %s/%s", len(candidates), len(tree), owner, repo)

    files: list[RepoFile] = []
    headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {settings.GITHUB_TOKEN}"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        for item in candidates:
            url = f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{item['path']}"
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                # Decode base64 content
                raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
                files.append(RepoFile(path=item["path"], content=raw, size=len(raw)))
            except (httpx.HTTPStatusError, Exception) as exc:
                logger.warning("Skipping %s: %s", item["path"], exc)
                continue

    return files


async def fetch_repo(repo_url: str) -> list[RepoFile]:
    """
    High-level convenience: URL in → list of RepoFile out.
    """
    owner, repo = parse_owner_repo(repo_url)
    tree = await fetch_repo_tree(owner, repo)
    return await fetch_file_contents(owner, repo, tree)
