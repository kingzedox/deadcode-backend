"""
DeadCode — Configuration Module
Loads environment variables and provides app-wide settings.
"""

import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv()


class Settings:
    """Centralised application settings pulled from environment variables."""

    # Groq LLM
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    # GitHub REST API (unauthenticated for public repos)
    GITHUB_API_BASE: str = "https://api.github.com"

    # Limits — keep requests reasonable for the free tiers
    MAX_FILES_TO_FETCH: int = 40          # max individual files to download
    MAX_FILE_SIZE_BYTES: int = 100_000    # skip files larger than ~100 KB
    MAX_PROMPT_CHARS: int = 80_000        # ~20k tokens — fits in Groq's 128k context with headroom
    SUPPORTED_EXTENSIONS: set = {
        ".js", ".jsx", ".ts", ".tsx",     # JavaScript / TypeScript
        ".py",                             # Python
        ".java",                           # Java
        ".go",                             # Go
        ".rb",                             # Ruby
        ".rs",                             # Rust
        ".php",                            # PHP
        ".vue", ".svelte",                 # Frontend frameworks
    }


settings = Settings()
