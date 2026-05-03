"""
DeadCode — FastAPI Application Entry Point
Exposes:
  GET  /health   → liveness check
  POST /analyze  → main analysis pipeline
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.analyzer import analyze_repo
from app.github_service import fetch_repo
from app.schemas import AnalyzeRequest, AnalyzeResponse

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-24s  %(levelname)-7s  %(message)s",
)
logger = logging.getLogger("deadcode")

# ─── App Setup ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="DeadCode API",
    description=(
        "Analyze public GitHub repos for deprecated APIs, outdated patterns, "
        "and security risks — then generate a ready-to-run JSSG codemod to fix them."
    ),
    version="1.0.0",
)

# CORS — allow all origins (hackathon mode)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health():
    """Simple liveness probe."""
    return {"status": "ok", "service": "deadcode-api", "version": "1.0.0"}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
async def analyze(payload: AnalyzeRequest):
    """
    Full analysis pipeline:
    1. Fetch the repo's file tree from GitHub
    2. Download relevant source files
    3. Send code to Groq for analysis
    4. Return structured risk report + JSSG codemod
    """
    t0 = time.perf_counter()
    logger.info("▸ Analyze request: repo=%s  scan=%s", payload.repo_url, payload.scan_type)

    # ── Step 1+2: Fetch repo ────────────────────────────────────────────────
    try:
        files = await fetch_repo(payload.repo_url)
    except Exception as exc:
        logger.error("GitHub fetch failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch repository from GitHub: {exc}",
        )

    logger.info("  Fetched %d files in %.1fs", len(files), time.perf_counter() - t0)

    # ── Step 3+4: Analyze with LLM ─────────────────────────────────────────
    try:
        result = await analyze_repo(files, payload.scan_type, payload.repo_url)
    except RuntimeError as exc:
        # Missing API key or config error
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.error("Analysis failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"LLM analysis failed: {exc}",
        )

    elapsed = time.perf_counter() - t0
    logger.info(
        "  ✔ Done in %.1fs — %d issues, blast_radius=%s",
        elapsed,
        result.risk_report.total_issues,
        result.blast_radius,
    )

    return result
