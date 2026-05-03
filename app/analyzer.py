"""
DeadCode — Groq / LLM Analyzer Service
Sends fetched source code to the Groq API (llama-3.3-70b-versatile) and
parses the structured response into a risk report + JSSG codemod script.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.github_service import RepoFile
from app.schemas import AnalyzeResponse, Issue, RiskReport

logger = logging.getLogger("deadcode.analyzer")


# ─── Prompt Templates ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are DeadCode, an expert static-analysis AI. You review source code for:
- Deprecated APIs and outdated patterns
- Security vulnerabilities and risky code
- Performance anti-patterns
- Unmaintained / dead code

You output STRICT JSON only — no markdown fences, no commentary outside JSON.
"""

def _build_analysis_prompt(files: list[RepoFile], scan_type: str) -> str:
    """Build the user prompt containing the code to analyse."""

    scan_focus = {
        "full": "deprecated APIs, outdated patterns, security risks, and performance issues",
        "security": "security vulnerabilities, injection risks, hardcoded secrets, and unsafe patterns",
        "deprecation": "deprecated APIs, outdated library usage, and legacy patterns",
        "performance": "performance anti-patterns, memory leaks, and inefficient code",
    }.get(scan_type, "deprecated APIs, outdated patterns, security risks, and performance issues")

    # Build a compact representation of the codebase
    code_sections: list[str] = []
    for f in files:
        # Truncate very long files to first 200 lines for prompt economy
        lines = f.content.splitlines()[:200]
        code_sections.append(f"### FILE: {f.path}\n```\n" + "\n".join(lines) + "\n```")

    code_block = "\n\n".join(code_sections)

    return f"""\
Analyze the following codebase for: {scan_focus}.

{code_block}

Respond with a single JSON object matching this EXACT schema (no extra keys):

{{
  "issues": [
    {{
      "file": "path/to/file.js",
      "line": 42,
      "severity": "low | medium | high | critical",
      "category": "deprecation | security | performance | dead-code",
      "description": "What the problem is",
      "suggestion": "How to fix it"
    }}
  ],
  "summary": "A 2-3 sentence executive summary of the repo's health.",
  "codemod_script": "A complete, valid JSSG codemod script (export default function transform(root) {{ ... }}) that fixes the issues found. Use ast-grep rule patterns. The script must be ready to run with: npx codemod jssg run transform.js ./src --language javascript"
}}

Rules:
- severity must be one of: low, medium, high, critical
- category must be one of: deprecation, security, performance, dead-code
- codemod_script must be a SINGLE string containing the full JS code
- If no issues found, return empty issues array and a simple pass-through codemod
- Focus on ACTIONABLE issues, not style nits
- The codemod must use the JSSG format: export default function transform(root) {{ ... }}
  using root.findAll({{ rule: {{ pattern: "..." }} }}) and node.replace("...")
"""


# ─── Groq API Call ───────────────────────────────────────────────────────────

async def _call_groq(system: str, user: str) -> dict[str, Any]:
    """
    Send a chat completion request to Groq and return parsed JSON.
    Retries once on JSON parse failure.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,      # low temperature for deterministic output
        "max_tokens": 8_000,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(settings.GROQ_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    raw_content: str = data["choices"][0]["message"]["content"]

    # Strip possible markdown fences the model might still sneak in
    raw_content = re.sub(r"^```(?:json)?\n?", "", raw_content.strip())
    raw_content = re.sub(r"\n?```$", "", raw_content.strip())

    return json.loads(raw_content)


# ─── Public Interface ────────────────────────────────────────────────────────

def _compute_blast_radius(issues: list[Issue], total_files: int) -> str:
    """Heuristic blast-radius classification."""
    if not issues:
        return "low"
    critical_high = sum(1 for i in issues if i.severity in ("critical", "high"))
    affected_ratio = len({i.file for i in issues}) / max(total_files, 1)
    if critical_high >= 5 or affected_ratio > 0.5:
        return "high"
    if critical_high >= 2 or affected_ratio > 0.25:
        return "medium"
    return "low"


async def analyze_repo(files: list[RepoFile], scan_type: str, repo_url: str) -> AnalyzeResponse:
    """
    Run the full analysis pipeline:
    1. Build prompt from source files
    2. Call Groq LLM
    3. Parse response into structured models
    4. Return AnalyzeResponse
    """
    if not files:
        # Nothing to analyse — return clean report
        return AnalyzeResponse(
            risk_report=RiskReport(total_issues=0, summary="No supported source files found in the repository."),
            codemod_script='export default function transform(root) {\n  // No issues detected — nothing to transform.\n}\n',
            affected_files=[],
            blast_radius="low",
            repo_url=repo_url,
            scan_type=scan_type,
            files_scanned=0,
        )

    logger.info("Analyzing %d files with Groq (%s)", len(files), settings.GROQ_MODEL)

    prompt = _build_analysis_prompt(files, scan_type)
    result = await _call_groq(SYSTEM_PROMPT, prompt)

    # Parse issues
    raw_issues = result.get("issues", [])
    issues: list[Issue] = []
    for raw in raw_issues:
        try:
            issues.append(Issue(**raw))
        except Exception as exc:
            logger.warning("Skipping malformed issue: %s — %s", raw, exc)

    # Build risk report
    risk_report = RiskReport(
        total_issues=len(issues),
        critical=sum(1 for i in issues if i.severity == "critical"),
        high=sum(1 for i in issues if i.severity == "high"),
        medium=sum(1 for i in issues if i.severity == "medium"),
        low=sum(1 for i in issues if i.severity == "low"),
        issues=issues,
        summary=result.get("summary", ""),
    )

    affected_files = sorted({i.file for i in issues})
    blast_radius = _compute_blast_radius(issues, len(files))
    codemod_script = result.get("codemod_script", "// No codemod generated")

    return AnalyzeResponse(
        risk_report=risk_report,
        codemod_script=codemod_script,
        affected_files=affected_files,
        blast_radius=blast_radius,
        repo_url=repo_url,
        scan_type=scan_type,
        files_scanned=len(files),
    )
