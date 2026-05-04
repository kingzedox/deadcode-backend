# 🧟 DeadCode

> **Boring AI Hackathon by Codemod.com**
> Scan public GitHub repos for dead code, deprecated APIs, and security risks — then generate a ready-to-run JSSG codemod to fix them.
> ## Live Demo: 

https://deadcodescan.vercel.app

> ## Frontend:

https://github.com/kingzedox/deadcode-frontend
---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Groq API key
cp .env.example .env
# Edit .env and add your key from https://console.groq.com/keys

# 3. Run the server
python run.py
# → http://localhost:8000
```

## 📡 API Endpoints

### `GET /health`
Liveness probe.

```json
{ "status": "ok", "service": "deadcode-api", "version": "1.0.0" }
```

### `POST /analyze`
Analyze a public GitHub repo and generate a JSSG codemod.

**Request:**
```json
{
  "repo_url": "https://github.com/owner/repo",
  "scan_type": "full"
}
```

`scan_type` options: `full` | `security` | `deprecation` | `performance`

**Response:**
```json
{
  "risk_report": {
    "total_issues": 5,
    "critical": 1,
    "high": 2,
    "medium": 1,
    "low": 1,
    "issues": [ ... ],
    "summary": "..."
  },
  "codemod_script": "export default function transform(root) { ... }",
  "affected_files": ["src/index.js", "src/utils.js"],
  "blast_radius": "medium",
  "repo_url": "https://github.com/owner/repo",
  "scan_type": "full",
  "files_scanned": 23
}
```

### Running the generated codemod

```bash
# Save the codemod_script to a file
echo "$CODEMOD_SCRIPT" > transform.js

# Run it with Codemod's CLI
npx codemod jssg run transform.js ./src --language javascript
```

## 🏗️ Project Structure

```
deadcode/
├── app/
│   ├── __init__.py          # Package init
│   ├── main.py              # FastAPI app, routes, CORS
│   ├── config.py            # Settings from .env
│   ├── schemas.py           # Pydantic request/response models
│   ├── github_service.py    # GitHub REST API integration
│   └── analyzer.py          # Groq LLM analysis + codemod generation
├── run.py                   # Dev server launcher
├── requirements.txt
├── .env.example
└── .gitignore
```

## 🔑 Environment Variables

| Variable       | Required | Description                          |
|----------------|----------|--------------------------------------|
| `GROQ_API_KEY` | ✅       | API key from https://console.groq.com |

## 📜 License

MIT — Ship fast, hack hard. 🏴‍☠️
=======
# deadcode
>>>>>>> 8cf2735841507ed8c31803b5f5ca536f56752204
