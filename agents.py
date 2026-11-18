"""
DevPulse AI — Agent Module
===========================
Autonomous multi-agent system for GitHub repository analysis.
Uses Google Gemini API for intelligent code analysis and the
GitHub REST API (unauthenticated, public repos) for live data.

Agents:
  • OrchestratorAgent        – interprets user goals, plans workflow
  • CodeSecurityAuditorAgent – scans for vulnerabilities, bugs, quality
  • DocumentationAgent       – generates architecture docs, README, tasks
  • GitHubTool               – fetches repo metadata, file trees, source
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests
from google import genai
from google.genai import types


# ════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════

GITHUB_API = "https://api.github.com"
RAW_GH = "https://raw.githubusercontent.com"
DEFAULT_MODEL = "gemini-2.0-flash"

MAX_FILE_SIZE = 80_000       # skip individual files larger than this
MAX_TOTAL_CONTENT = 120_000  # cap cumulative fetched content
MAX_FILES_TO_FETCH = 15

DEMO_REPO_URL = "https://github.com/tiangolo/fastapi"

# Patterns for files worth fetching
KEY_PATTERNS: list[str] = [
    r"^README\.md$", r"^readme\.md$",
    r"^setup\.py$", r"^pyproject\.toml$",
    r"^requirements.*\.txt$", r"^Pipfile$",
    r"^package\.json$", r"^Cargo\.toml$", r"^go\.mod$",
    r"^Dockerfile$", r"^docker-compose\.ya?ml$",
    r"^\.github/workflows/.*\.ya?ml$",
    r"^Makefile$", r"^\.env\.example$", r"^\.env$",
    r"^app\.(py|js|ts)$", r"^main\.(py|js|ts|go|rs)$",
    r"^index\.(py|js|ts)$", r"^server\.(py|js|ts)$",
    r"^manage\.py$",
    r"^config.*\.(py|json|ya?ml|toml)$",
    r"^settings\.(py|json|ya?ml|toml)$",
    r"^src/.*\.(py|js|ts|go|rs)$",
    r"^lib/.*\.(py|js|ts)$",
]

SOURCE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".cpp", ".h", ".cs", ".swift", ".kt",
}


# ════════════════════════════════════════════════════════════════
#  DATA MODELS
# ════════════════════════════════════════════════════════════════

@dataclass
class RepoMetadata:
    name: str = ""
    full_name: str = ""
    description: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: str = "Unknown"
    topics: List[str] = field(default_factory=list)
    license_name: str = "None"
    default_branch: str = "main"
    created_at: str = ""
    updated_at: str = ""
    size: int = 0
    html_url: str = ""
    has_wiki: bool = False
    watchers: int = 0


@dataclass
class RepoFile:
    path: str
    content: str
    size: int


@dataclass
class TreeEntry:
    path: str
    type: str          # "blob" | "tree"
    size: int = 0


@dataclass
class AgentDecision:
    agent: str
    action: str
    reasoning: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class SecurityFinding:
    severity: str      # HIGH | MEDIUM | LOW
    title: str
    description: str
    file_path: str
    recommendation: str


@dataclass
class TaskItem:
    priority: str      # P0 | P1 | P2
    title: str
    description: str
    category: str


# ════════════════════════════════════════════════════════════════
#  UTILITY HELPERS
# ════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> Any | None:
    """Parse JSON from raw text, markdown-fenced code blocks, or substring search."""
    if not text:
        return None

    # 1. Direct parse
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Markdown fenced code blocks (with or without indentation)
    matches = re.findall(r"```(?:json)?\s*[\r\n]+(.*?)[\r\n]+\s*```", text, re.S)
    for candidate in matches:
        try:
            return json.loads(candidate.strip())
        except (json.JSONDecodeError, ValueError):
            continue

    # 3. Substring between first { or [ and last } or ]
    first_brace = text.find("{")
    first_bracket = text.find("[")
    starts = [i for i in (first_brace, first_bracket) if i != -1]
    if starts:
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end > start:
            try:
                return json.loads(text[start : end + 1].strip())
            except (json.JSONDecodeError, ValueError):
                pass

    return None


def summarize_tree(tree: List[TreeEntry], cap: int = 60) -> str:
    """Human-readable summary of a repo tree for LLM context."""
    dirs: set[str] = set()
    top_files: list[str] = []
    for e in tree:
        if e.type == "tree":
            dirs.add(e.path.split("/")[0])
        elif e.path.count("/") == 0:
            top_files.append(e.path)
    lines = ["**Top-level directories:**"]
    for d in sorted(dirs)[:25]:
        lines.append(f"  • `{d}/`")
    lines.append("\n**Root files:**")
    for f in sorted(top_files)[:20]:
        lines.append(f"  • `{f}`")
    blob_count = sum(1 for e in tree if e.type == "blob")
    lines.append(f"\n_Total: {len(tree)} entries, {blob_count} files_")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
#  GITHUB TOOL
# ════════════════════════════════════════════════════════════════

class GitHubToolError(Exception):
    """Raised on non-recoverable GitHub API errors."""


class RateLimitError(GitHubToolError):
    """Raised when GitHub returns 403 / rate-limit."""


class GitHubTool:
    """Fetches live data from the GitHub REST API (no token needed for
    public repos).  Includes a full fallback dataset so the demo never
    fails during a live presentation."""

    # ── URL parsing ───────────────────────────────────────────
    @staticmethod
    def parse_url(url: str) -> Tuple[str, str]:
        """Return (owner, repo) from any GitHub URL or 'owner/repo'."""
        url = url.strip().rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        m = re.match(
            r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)", url
        )
        if m:
            return m.group(1), m.group(2)
        parts = url.split("/")
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1]
        raise GitHubToolError(
            f"Cannot parse GitHub URL: {url!r}. "
            "Expected https://github.com/owner/repo"
        )

    # ── Low-level GET ─────────────────────────────────────────
    @staticmethod
    def _get(endpoint: str, timeout: int = 15) -> dict | list:
        url = f"{GITHUB_API}{endpoint}" if endpoint.startswith("/") else endpoint
        try:
            r = requests.get(url, timeout=timeout, headers={
                "Accept": "application/vnd.github+json",
            })
        except requests.RequestException as exc:
            raise GitHubToolError(f"Network error: {exc}") from exc
        if r.status_code == 403:
            raise RateLimitError("GitHub API rate limit exceeded (60 req/hr for unauthenticated).")
        if r.status_code == 404:
            raise GitHubToolError("Repository not found (404). Is it public?")
        if r.status_code != 200:
            raise GitHubToolError(f"GitHub API error {r.status_code}: {r.text[:300]}")
        return r.json()

    # ── Metadata ──────────────────────────────────────────────
    def fetch_metadata(self, owner: str, repo: str) -> RepoMetadata:
        data = self._get(f"/repos/{owner}/{repo}")
        lic = data.get("license") or {}
        return RepoMetadata(
            name=data.get("name", repo),
            full_name=data.get("full_name", f"{owner}/{repo}"),
            description=data.get("description", "") or "",
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            open_issues=data.get("open_issues_count", 0),
            language=data.get("language", "Unknown") or "Unknown",
            topics=data.get("topics", []),
            license_name=lic.get("spdx_id", "None") or "None",
            default_branch=data.get("default_branch", "main"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            size=data.get("size", 0),
            html_url=data.get("html_url", ""),
            has_wiki=data.get("has_wiki", False),
            watchers=data.get("watchers_count", 0),
        )

    # ── File tree ─────────────────────────────────────────────
    def fetch_tree(self, owner: str, repo: str, branch: str = "main") -> List[TreeEntry]:
        data = self._get(f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1")
        entries = []
        for item in data.get("tree", []):
            entries.append(TreeEntry(
                path=item["path"],
                type=item["type"],
                size=item.get("size", 0),
            ))
        return entries

    # ── Single file content ───────────────────────────────────
    @staticmethod
    def fetch_file_content(owner: str, repo: str, path: str,
                           branch: str = "main") -> str:
        url = f"{RAW_GH}/{owner}/{repo}/{branch}/{path}"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        return ""

    # ── Intelligent key-file selection ────────────────────────
    @staticmethod
    def select_key_files(tree: List[TreeEntry]) -> List[str]:
        """Pick the most informative files for analysis."""
        selected: list[str] = []
        source_candidates: list[Tuple[int, str]] = []  # (depth, path)

        for entry in tree:
            if entry.type != "blob":
                continue
            # Match against priority patterns
            if any(re.match(p, entry.path, re.I) for p in KEY_PATTERNS):
                if entry.size <= MAX_FILE_SIZE:
                    selected.append(entry.path)
                continue
            # Collect source files for secondary selection
            ext = "." + entry.path.rsplit(".", 1)[-1] if "." in entry.path else ""
            if ext in SOURCE_EXTS and entry.size <= MAX_FILE_SIZE:
                depth = entry.path.count("/")
                source_candidates.append((depth, entry.path))

        # Add shallowest source files up to the cap
        source_candidates.sort()
        remaining = MAX_FILES_TO_FETCH - len(selected)
        for _, path in source_candidates[:max(0, remaining)]:
            selected.append(path)

        return selected[:MAX_FILES_TO_FETCH]

    # ── Batch fetch ───────────────────────────────────────────
    def fetch_key_files(self, owner: str, repo: str,
                        tree: List[TreeEntry],
                        branch: str = "main") -> List[RepoFile]:
        paths = self.select_key_files(tree)
        files: list[RepoFile] = []
        total = 0
        for p in paths:
            if total >= MAX_TOTAL_CONTENT:
                break
            content = self.fetch_file_content(owner, repo, p, branch)
            if content:
                size = len(content.encode())
                files.append(RepoFile(path=p, content=content, size=size))
                total += size
        return files

    # ── Health score ──────────────────────────────────────────
    @staticmethod
    def compute_health_score(
        meta: RepoMetadata,
        tree: List[TreeEntry],
        files: List[RepoFile],
    ) -> Tuple[int, Dict[str, int]]:
        paths = {e.path.lower() for e in tree}
        blob_names = {e.path.split("/")[-1].lower() for e in tree if e.type == "blob"}
        breakdown: Dict[str, int] = {}

        breakdown["README"] = 15 if any("readme" in p for p in blob_names) else 0
        breakdown["License"] = 10 if (
            meta.license_name not in ("None", "", None)
            or any("license" in p for p in blob_names)
        ) else 0
        breakdown["CI/CD"] = 10 if any(
            ".github/workflows" in p or "jenkinsfile" in p or ".gitlab-ci" in p
            for p in paths
        ) else 0
        breakdown["Tests"] = 10 if any(
            "test" in p.split("/")[0] for p in paths
        ) or any("test_" in p or "_test." in p for p in blob_names) else 0

        dep_names = {
            "requirements.txt", "setup.py", "pyproject.toml", "package.json",
            "cargo.toml", "go.mod", "gemfile", "pom.xml", "build.gradle",
        }
        breakdown["Dependencies"] = 10 if dep_names & blob_names else 0
        breakdown["Docker"] = 5 if any(
            "dockerfile" in p or "docker-compose" in p for p in blob_names
        ) else 0

        if meta.stars >= 1000:
            breakdown["Community"] = 15
        elif meta.stars >= 100:
            breakdown["Community"] = 10
        elif meta.stars >= 10:
            breakdown["Community"] = 5
        else:
            breakdown["Community"] = 2

        breakdown["Gitignore"] = 5 if ".gitignore" in blob_names else 0
        breakdown["Description"] = 5 if meta.description else 0
        breakdown["Topics"] = 5 if meta.topics else 0

        raw = sum(breakdown.values())          # max theoretical 90
        score = min(100, int(raw * 100 / 90))
        return score, breakdown

    # ── Fallback demo data ────────────────────────────────────
    @staticmethod
    def get_demo_fallback() -> Tuple[RepoMetadata, List[TreeEntry], List[RepoFile]]:
        """Return realistic cached data so the demo never fails."""
        meta = RepoMetadata(
            name="fastapi",
            full_name="tiangolo/fastapi",
            description="FastAPI framework, high performance, easy to learn, fast to code, ready for production",
            stars=79500, forks=6700, open_issues=530,
            language="Python",
            topics=["python", "api", "rest", "fastapi", "async", "openapi", "pydantic"],
            license_name="MIT",
            default_branch="master",
            created_at="2018-12-08T00:00:00Z",
            updated_at="2026-11-15T00:00:00Z",
            size=35800,
            html_url="https://github.com/tiangolo/fastapi",
            has_wiki=False, watchers=79500,
        )

        tree_paths = [
            ("fastapi", "tree"), ("fastapi/__init__.py", "blob"),
            ("fastapi/applications.py", "blob"), ("fastapi/routing.py", "blob"),
            ("fastapi/security", "tree"), ("fastapi/security/__init__.py", "blob"),
            ("fastapi/security/oauth2.py", "blob"),
            ("fastapi/middleware", "tree"), ("fastapi/middleware/cors.py", "blob"),
            ("fastapi/dependencies", "tree"),
            ("tests", "tree"), ("tests/test_application.py", "blob"),
            ("tests/test_security.py", "blob"),
            ("docs", "tree"), ("docs/en", "tree"),
            (".github", "tree"), (".github/workflows", "tree"),
            (".github/workflows/ci.yml", "blob"),
            ("README.md", "blob"), ("pyproject.toml", "blob"),
            ("requirements.txt", "blob"), ("Makefile", "blob"),
            ("LICENSE", "blob"), (".gitignore", "blob"),
            ("scripts", "tree"), ("scripts/lint.sh", "blob"),
            ("docs_src", "tree"), ("docs_src/security", "tree"),
        ]
        tree = [TreeEntry(path=p, type=t, size=500) for p, t in tree_paths]

        demo_app = '''\
"""FastAPI Demo Application — illustrative sample for DevPulse analysis."""
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, os, hashlib

app = FastAPI(title="Demo API", version="0.1.0")

# ⚠ CORS wildcard — allows every origin
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

SECRET_KEY = "changeme-insecure-key-12345"   # ⚠ hardcoded secret
DB_PATH = os.getenv("DB_PATH", "app.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

@app.get("/users/{user_id}")
def get_user(user_id: str, db=Depends(get_db)):
    # ⚠ SQL injection — string interpolation
    row = db.execute(f"SELECT * FROM users WHERE id = \\'{user_id}\\'").fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return {"user": row}

@app.post("/login")
def login(username: str = Query(...), password: str = Query(...),
          db=Depends(get_db)):
    # ⚠ password in query string, no rate limiting
    hashed = hashlib.md5(password.encode()).hexdigest()   # ⚠ weak hash
    row = db.execute(
        f"SELECT * FROM users WHERE username=\\'{username}\\' "
        f"AND password_hash=\\'{hashed}\\'"
    ).fetchone()
    if not row:
        raise HTTPException(401, "Bad credentials")
    return {"token": SECRET_KEY + str(row[0])}   # ⚠ insecure token

@app.get("/files")
def list_files(directory: str = Query(".")):
    # ⚠ path traversal — no sanitisation
    return {"files": os.listdir(directory)}

@app.get("/health")
def health():
    return {"status": "ok"}
'''

        demo_requirements = "fastapi>=0.100.0\nuvicorn[standard]>=0.23.0\npydantic>=2.0\n" \
                            "python-multipart>=0.0.6\nsqlite3\nrequests\n"

        demo_pyproject = '''\
[build-system]
requires = ["flit_core >=3.2,<4"]
build-backend = "flit_core.buildapi"

[project]
name = "fastapi"
version = "0.104.0"
description = "FastAPI framework"
requires-python = ">=3.8"
license = {text = "MIT"}
'''

        files = [
            RepoFile("app.py", demo_app, len(demo_app)),
            RepoFile("requirements.txt", demo_requirements, len(demo_requirements)),
            RepoFile("pyproject.toml", demo_pyproject, len(demo_pyproject)),
        ]
        return meta, tree, files


# ════════════════════════════════════════════════════════════════
#  BASE AGENT
# ════════════════════════════════════════════════════════════════

class BaseAgent:
    """Shared Gemini client, decision logging, and retry logic."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.decisions: list[AgentDecision] = []

    def _log(self, action: str, reasoning: str):
        self.decisions.append(AgentDecision(
            agent=self.__class__.__name__, action=action, reasoning=reasoning,
        ))

    def _call(self, prompt: str, *, system: str = "",
              temperature: float = 0.35, retries: int = 2) -> str:
        cfg = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )
        last_err = ""
        for attempt in range(1, retries + 2):
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=prompt, config=cfg,
                )
                if resp and resp.text:
                    return resp.text
                last_err = "Empty response from Gemini"
            except Exception as exc:            # noqa: BLE001
                last_err = str(exc)
                if attempt <= retries:
                    time.sleep(1.5 * attempt)
        return f"[Agent error after {retries+1} attempts: {last_err}]"


# ════════════════════════════════════════════════════════════════
#  ORCHESTRATOR AGENT
# ════════════════════════════════════════════════════════════════

class OrchestratorAgent(BaseAgent):
    """Interprets the user's goal and the repo context to produce a
    prioritised workflow plan for the downstream agents."""

    SYSTEM = (
        "You are the **Orchestrator Agent** in the DevPulse AI multi-agent "
        "system.  Given a user goal, repository metadata, and a file-tree "
        "summary, produce a clear, numbered workflow plan.  For each step "
        "explain *what* to do and *why*.  Prioritise steps that best serve "
        "the user's stated goal.  Be concise but thorough."
    )

    def plan(self, goal: str, meta: RepoMetadata,
             tree: List[TreeEntry]) -> str:
        tree_summary = summarize_tree(tree)
        prompt = (
            f"## User Goal\n{goal}\n\n"
            f"## Repository\n"
            f"- **Name:** {meta.full_name}\n"
            f"- **Language:** {meta.language}\n"
            f"- **Description:** {meta.description}\n"
            f"- **Stars:** {meta.stars:,}  |  **Forks:** {meta.forks:,}  "
            f"|  **Open Issues:** {meta.open_issues:,}\n"
            f"- **License:** {meta.license_name}  |  "
            f"**Size:** {meta.size:,} KB\n\n"
            f"## File Structure\n{tree_summary}\n\n"
            "---\n"
            "Produce a **numbered workflow plan** (5-8 steps). "
            "For each step state: the responsible agent, the action, "
            "files/areas to focus on, and a one-line *reasoning* why "
            "this step matters for the user's goal."
        )
        plan_text = self._call(prompt, system=self.SYSTEM, temperature=0.3)
        self._log(
            "Generated workflow plan",
            f"Planned analysis for '{meta.full_name}' "
            f"targeting user goal: \"{goal[:80]}…\"",
        )
        return plan_text


# ════════════════════════════════════════════════════════════════
#  CODE & SECURITY AUDITOR AGENT
# ════════════════════════════════════════════════════════════════

class CodeSecurityAuditorAgent(BaseAgent):
    """Scans fetched source files for security vulnerabilities, bugs,
    anti-patterns, and code-quality issues."""

    SYSTEM = (
        "You are a **Senior Security Auditor & Code Reviewer**.  "
        "Analyse the provided source files for:\n"
        "• Security vulnerabilities (injections, hardcoded secrets, "
        "insecure crypto, path traversal, SSRF, XSS, CSRF, …)\n"
        "• Bugs & logic errors\n"
        "• Anti-patterns & code smells\n\n"
        "Return your findings as **valid JSON** (no markdown fences) with "
        'the schema:\n```json\n{"summary":"…","findings":[{"severity":'
        '"HIGH|MEDIUM|LOW","title":"…","description":"…",'
        '"file_path":"…","recommendation":"…"}]}\n```'
    )

    def audit(
        self, files: List[RepoFile], meta: RepoMetadata,
        goal: str, plan: str,
    ) -> Tuple[List[SecurityFinding], str]:
        if not files:
            return [], "No source files available for audit."

        files_block = "\n\n".join(
            f"### `{f.path}` ({f.size:,} bytes)\n```\n{f.content[:12000]}\n```"
            for f in files
        )
        prompt = (
            f"## Context\n"
            f"Repository: **{meta.full_name}** ({meta.language})\n"
            f"User goal: {goal}\n\n"
            f"## Orchestrator Focus\n{plan[:1500]}\n\n"
            f"## Source Files\n{files_block}\n\n"
            "---\n"
            "Produce **valid JSON** (no markdown fences) with your security "
            "& quality audit.  Include at least one finding per analysed file "
            "if issues exist.  Use exact file paths."
        )
        raw = self._call(prompt, system=self.SYSTEM, temperature=0.2)
        findings, summary = self._parse(raw)
        self._log(
            f"Completed audit — {len(findings)} findings",
            f"HIGH={sum(1 for f in findings if f.severity=='HIGH')} "
            f"MED={sum(1 for f in findings if f.severity=='MEDIUM')} "
            f"LOW={sum(1 for f in findings if f.severity=='LOW')}",
        )
        return findings, summary

    # ── Parse Gemini response ─────────────────────────────────
    @staticmethod
    def _parse(raw: str) -> Tuple[List[SecurityFinding], str]:
        data = _extract_json(raw)
        if data and isinstance(data, dict):
            summary = data.get("summary", "")
            findings = []
            for f in data.get("findings", []):
                findings.append(SecurityFinding(
                    severity=str(f.get("severity", "MEDIUM")).upper(),
                    title=f.get("title", "Untitled"),
                    description=f.get("description", ""),
                    file_path=f.get("file_path", "unknown"),
                    recommendation=f.get("recommendation", ""),
                ))
            return findings, summary
        # Fallback: treat the entire response as a summary
        return [], raw[:2000]


# ════════════════════════════════════════════════════════════════
#  DOCUMENTATION & ACTION-PLANNER AGENT
# ════════════════════════════════════════════════════════════════

class DocumentationAgent(BaseAgent):
    """Generates architecture docs, README, and a prioritised task list."""

    # ── Architecture doc ──────────────────────────────────────
    def generate_architecture(
        self, files: List[RepoFile], meta: RepoMetadata,
        tree: List[TreeEntry], security_summary: str,
    ) -> str:
        tree_summary = summarize_tree(tree)
        files_block = "\n\n".join(
            f"### `{f.path}`\n```\n{f.content[:6000]}\n```" for f in files[:8]
        )
        prompt = (
            f"## Repository\n{meta.full_name} — {meta.description}\n"
            f"Language: {meta.language} | Stars: {meta.stars:,}\n\n"
            f"## Structure\n{tree_summary}\n\n"
            f"## Key Files\n{files_block}\n\n"
            f"## Security Summary\n{security_summary[:800]}\n\n"
            "---\n"
            "Write a professional **Architecture & Design Document** in "
            "Markdown covering:\n"
            "1. System Overview\n"
            "2. Component Breakdown (modules, responsibilities)\n"
            "3. Technology Stack\n"
            "4. Data Flow description\n"
            "5. Key Design Patterns\n"
            "Be concise, insightful, and reference actual file paths."
        )
        doc = self._call(prompt, system=(
            "You are a senior software architect writing clear, "
            "professional technical documentation."
        ))
        self._log("Generated architecture document",
                  "Analysed components, tech stack, and data flow.")
        return doc

    # ── README generation ─────────────────────────────────────
    def generate_readme(
        self, meta: RepoMetadata, architecture: str,
        findings: List[SecurityFinding],
    ) -> str:
        finding_summary = "\n".join(
            f"- [{f.severity}] {f.title}" for f in findings[:10]
        )
        prompt = (
            f"## Repository\n{meta.full_name}: {meta.description}\n"
            f"Language: {meta.language} | License: {meta.license_name}\n\n"
            f"## Architecture Highlights\n{architecture[:2000]}\n\n"
            f"## Known Issues\n{finding_summary}\n\n"
            "---\n"
            "Generate a polished **README.md** with:\n"
            "• Project title & badges (shields.io style in markdown)\n"
            "• Overview / Features\n"
            "• Quick Start (install + run)\n"
            "• Project Structure summary\n"
            "• Contributing guidelines (brief)\n"
            "• License\n"
            "Output raw Markdown only."
        )
        readme = self._call(prompt, system=(
            "You are a developer-relations expert writing engaging, "
            "informative open-source README files."
        ))
        self._log("Generated README.md",
                  "Created installation, usage, and contribution sections.")
        return readme

    # ── Task checklist ────────────────────────────────────────
    def generate_tasks(
        self, findings: List[SecurityFinding], architecture: str,
        goal: str, meta: RepoMetadata,
    ) -> List[TaskItem]:
        finding_lines = "\n".join(
            f"- [{f.severity}] {f.title} in `{f.file_path}`"
            for f in findings[:15]
        )
        prompt = (
            f"## Context\n"
            f"Repo: {meta.full_name} ({meta.language})\n"
            f"User goal: {goal}\n\n"
            f"## Security Findings\n{finding_lines}\n\n"
            f"## Architecture Notes\n{architecture[:1500]}\n\n"
            "---\n"
            "Produce a **prioritised task checklist** as valid JSON "
            "(no markdown fences):\n"
            '```json\n[{"priority":"P0|P1|P2","title":"…",'
            '"description":"…","category":"Security|Performance|'
            'Documentation|Testing|DevOps"}]\n```\n'
            "Include 8-15 tasks.  P0 = critical/immediate, P1 = important, "
            "P2 = nice-to-have."
        )
        raw = self._call(prompt, system=(
            "You are a senior engineering manager creating an actionable "
            "task backlog.  Return **valid JSON only**."
        ), temperature=0.25)
        tasks = self._parse_tasks(raw)
        self._log(f"Generated {len(tasks)} task items",
                  "Prioritised backlog based on audit + user goal.")
        return tasks

    @staticmethod
    def _parse_tasks(raw: str) -> List[TaskItem]:
        data = _extract_json(raw)
        if isinstance(data, list):
            return [
                TaskItem(
                    priority=str(t.get("priority", "P2")).upper(),
                    title=t.get("title", "Untitled"),
                    description=t.get("description", ""),
                    category=t.get("category", "General"),
                ) for t in data
            ]
        return [TaskItem("P1", "Review raw agent output",
                         raw[:500], "General")]


# ════════════════════════════════════════════════════════════════
#  FULL REPORT GENERATOR
# ════════════════════════════════════════════════════════════════

def build_full_report(
    meta: RepoMetadata,
    health_score: int,
    plan: str,
    findings: List[SecurityFinding],
    security_summary: str,
    architecture: str,
    readme: str,
    tasks: List[TaskItem],
    decisions: List[AgentDecision],
) -> str:
    """Compile every output into a single downloadable Markdown report."""
    sev_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
    pri_icon = {"P0": "🔴", "P1": "🟡", "P2": "🔵"}

    sections = [
        f"# DevPulse AI — Full Audit Report",
        f"**Repository:** [{meta.full_name}]({meta.html_url})  ",
        f"**Language:** {meta.language}  |  **Stars:** {meta.stars:,}  "
        f"|  **Forks:** {meta.forks:,}  |  **Health Score:** {health_score}/100\n",
        f"---\n## 1 · Orchestrator Workflow Plan\n{plan}\n",
        "---\n## 2 · Security & Code Audit\n",
        f"**Executive Summary:** {security_summary}\n",
    ]

    if findings:
        sections.append("| Severity | Title | File | Recommendation |")
        sections.append("|----------|-------|------|----------------|")
        for f in findings:
            icon = sev_icon.get(f.severity, "⚪")
            sections.append(
                f"| {icon} {f.severity} | {f.title} | `{f.file_path}` "
                f"| {f.recommendation} |"
            )
        sections.append("")
    else:
        sections.append("_No findings._\n")

    sections.append(f"---\n## 3 · Architecture Document\n{architecture}\n")
    sections.append(f"---\n## 4 · Auto-Generated README.md\n{readme}\n")
    sections.append("---\n## 5 · Prioritised Task Checklist\n")

    for t in tasks:
        icon = pri_icon.get(t.priority, "⚪")
        sections.append(f"- {icon} **[{t.priority}]** {t.title} "
                        f"({t.category}) — {t.description}")
    sections.append("")

    sections.append("---\n## 6 · Agent Decision Log\n")
    for d in decisions:
        sections.append(f"- **{d.agent}** → {d.action}  \n"
                        f"  _Reasoning:_ {d.reasoning}")
    sections.append(
        "\n---\n_Report generated by DevPulse AI — "
        "Autonomous GitHub Repo & Workflow Agent_\n"
    )
    return "\n".join(sections)
