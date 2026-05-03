"""
DeadCode — Pydantic Schemas
Request / response models for the /analyze endpoint.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator
import re


# ─── Request ────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Payload sent by the frontend to start an analysis."""

    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL, e.g. https://github.com/owner/repo",
        examples=["https://github.com/facebook/react"],
    )
    scan_type: str = Field(
        default="full",
        description="Type of scan to run: 'full', 'security', 'deprecation', or 'performance'",
        examples=["full"],
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Ensure the URL looks like a valid GitHub repo URL."""
        pattern = r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+/?$"
        if not re.match(pattern, v.strip().rstrip("/")):
            raise ValueError(
                "Invalid GitHub URL. Expected format: https://github.com/owner/repo"
            )
        return v.strip().rstrip("/")


# ─── Response sub-models ────────────────────────────────────────────────────

class Issue(BaseModel):
    """A single detected issue."""

    file: str
    line: int | None = None
    severity: Literal["low", "medium", "high", "critical"]
    category: str
    description: str
    suggestion: str


class RiskReport(BaseModel):
    """Aggregated risk report returned to the frontend."""

    total_issues: int
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    issues: list[Issue] = []
    summary: str = ""


class AnalyzeResponse(BaseModel):
    """Complete response payload for /analyze."""

    risk_report: RiskReport
    codemod_script: str
    affected_files: list[str]
    blast_radius: Literal["low", "medium", "high"]
    repo_url: str
    scan_type: str
    files_scanned: int
