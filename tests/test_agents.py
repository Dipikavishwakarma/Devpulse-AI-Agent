"""
DevPulse AI — Test Suite
=========================
Unit tests for GitHub URL parsing, fallback mode, health score,
file selection, agent response parsing, and report generation.
"""

from unittest.mock import MagicMock, patch
import pytest

from agents import (
    AgentDecision,
    CodeSecurityAuditorAgent,
    DocumentationAgent,
    GitHubTool,
    GitHubToolError,
    OrchestratorAgent,
    RateLimitError,
    RepoFile,
    RepoMetadata,
    SecurityFinding,
    TaskItem,
    TreeEntry,
    _extract_json,
    build_full_report,
    summarize_tree,
)


# ════════════════════════════════════════════════════════════════
# 1. GITHUB URL PARSER TESTS
# ════════════════════════════════════════════════════════════════

class TestGitHubUrlParser:
    """Tests for GitHubTool.parse_url handling diverse inputs."""

    def test_standard_https_url(self):
        owner, repo = GitHubTool.parse_url("https://github.com/tiangolo/fastapi")
        assert owner == "tiangolo"
        assert repo == "fastapi"

    def test_url_with_git_extension(self):
        owner, repo = GitHubTool.parse_url("https://github.com/pallets/flask.git")
        assert owner == "pallets"
        assert repo == "flask"

    def test_url_without_protocol(self):
        owner, repo = GitHubTool.parse_url("github.com/psf/black")
        assert owner == "psf"
        assert repo == "black"

    def test_shorthand_owner_repo(self):
        owner, repo = GitHubTool.parse_url("pydantic/pydantic")
        assert owner == "pydantic"
        assert repo == "pydantic"

    def test_trailing_slash_handling(self):
        owner, repo = GitHubTool.parse_url("https://github.com/streamlit/streamlit/")
        assert owner == "streamlit"
        assert repo == "streamlit"

    def test_deep_url_with_subpath(self):
        owner, repo = GitHubTool.parse_url("https://github.com/octocat/Hello-World/tree/master/src")
        assert owner == "octocat"
        assert repo == "Hello-World"

    def test_invalid_urls_raise_error(self):
        invalid_inputs = [
            "https://notgithub.com/user/repo",
            "justarepo",
            "",
            "   ",
            "https://google.com",
            "/onlyowner/",
        ]
        for url in invalid_inputs:
            with pytest.raises(GitHubToolError):
                GitHubTool.parse_url(url)


# ════════════════════════════════════════════════════════════════
# 2. FALLBACK MODE & HEALTH SCORE TESTS
# ════════════════════════════════════════════════════════════════

class TestFallbackAndHealthScore:
    """Tests for demo fallback dataset and health score calculation."""

    def test_demo_fallback_data_integrity(self):
        meta, tree, files = GitHubTool.get_demo_fallback()

        assert isinstance(meta, RepoMetadata)
        assert meta.name == "fastapi"
        assert meta.full_name == "tiangolo/fastapi"
        assert meta.stars >= 50000
        assert meta.language.lower() == "python"

        assert len(tree) > 10
        assert any(e.path == "README.md" for e in tree)

        assert len(files) >= 3
        file_names = [f.path for f in files]
        assert "app.py" in file_names
        assert "requirements.txt" in file_names

    def test_health_score_with_full_demo(self):
        meta, tree, files = GitHubTool.get_demo_fallback()
        score, breakdown = GitHubTool.compute_health_score(meta, tree, files)

        assert 0 <= score <= 100
        assert score >= 70  # Demo repo should have a strong health score
        assert "README" in breakdown
        assert "License" in breakdown
        assert "Community" in breakdown
        assert breakdown["README"] > 0
        assert breakdown["License"] > 0

    def test_health_score_minimal_repo(self):
        empty_meta = RepoMetadata(
            name="bare-bones",
            full_name="test/bare-bones",
            stars=0,
            license_name="None",
            description="",
        )
        empty_tree = [TreeEntry(path="script.py", type="blob", size=100)]
        empty_files = [RepoFile(path="script.py", content="print(1)", size=8)]

        score, breakdown = GitHubTool.compute_health_score(empty_meta, empty_tree, empty_files)
        assert score < 50
        assert breakdown["README"] == 0
        assert breakdown["License"] == 0
        assert breakdown["CI/CD"] == 0


# ════════════════════════════════════════════════════════════════
# 3. TREE SUMMARIZATION & FILE SELECTION
# ════════════════════════════════════════════════════════════════

class TestTreeProcessing:
    """Tests for file tree summarization and priority file selection."""

    def test_summarize_tree(self):
        tree = [
            TreeEntry(path="src", type="tree"),
            TreeEntry(path="src/main.py", type="blob", size=100),
            TreeEntry(path="README.md", type="blob", size=50),
            TreeEntry(path="pyproject.toml", type="blob", size=80),
        ]
        summary = summarize_tree(tree)
        assert "src/" in summary
        assert "README.md" in summary
        assert "4 entries" in summary

    def test_select_key_files_priority(self):
        tree = [
            TreeEntry(path="README.md", type="blob", size=500),
            TreeEntry(path="pyproject.toml", type="blob", size=200),
            TreeEntry(path="Dockerfile", type="blob", size=300),
            TreeEntry(path="app.py", type="blob", size=1000),
            TreeEntry(path="image.png", type="blob", size=50000),
            TreeEntry(path="tests/test_something.py", type="blob", size=400),
        ]
        selected = GitHubTool.select_key_files(tree)

        assert "README.md" in selected
        assert "pyproject.toml" in selected
        assert "Dockerfile" in selected
        assert "app.py" in selected
        # Non-source binaries should not be prioritized
        assert "image.png" not in selected


# ════════════════════════════════════════════════════════════════
# 4. JSON PARSING & AGENT PARSER TESTS
# ════════════════════════════════════════════════════════════════

class TestAgentParsers:
    """Tests for JSON extraction and agent response parsing."""

    def test_extract_json_from_plain_text(self):
        raw = '{"key": "value", "count": 42}'
        data = _extract_json(raw)
        assert data == {"key": "value", "count": 42}

    def test_extract_json_from_code_blocks(self):
        raw = 'Here is the result:\n```json\n{"status": "ok", "items": [1, 2]}\n```\nDone.'
        data = _extract_json(raw)
        assert data == {"status": "ok", "items": [1, 2]}

    def test_extract_json_invalid(self):
        assert _extract_json("Not a json at all") is None

    def test_security_auditor_parse(self):
        raw = """```json
        {
            "summary": "Critical vulnerabilities detected.",
            "findings": [
                {
                    "severity": "high",
                    "title": "SQL Injection",
                    "description": "User input directly formatted into query.",
                    "file_path": "app.py",
                    "recommendation": "Use parameterized queries."
                },
                {
                    "severity": "low",
                    "title": "Missing docstring",
                    "description": "Helper function lacks docs.",
                    "file_path": "utils.py",
                    "recommendation": "Add docstrings."
                }
            ]
        }
        ```"""
        findings, summary = CodeSecurityAuditorAgent._parse(raw)
        assert summary == "Critical vulnerabilities detected."
        assert len(findings) == 2
        assert findings[0].severity == "HIGH"
        assert findings[0].title == "SQL Injection"
        assert findings[0].file_path == "app.py"
        assert findings[1].severity == "LOW"

    def test_security_auditor_parse_fallback(self):
        raw = "Raw narrative security review without valid JSON."
        findings, summary = CodeSecurityAuditorAgent._parse(raw)
        assert findings == []
        assert "Raw narrative" in summary

    def test_documentation_parse_tasks(self):
        raw = """```json
        [
            {
                "priority": "P0",
                "title": "Fix SQL injection",
                "description": "Replace string formatting with parameterized query.",
                "category": "Security"
            },
            {
                "priority": "p1",
                "title": "Add CI workflow",
                "description": "Set up GitHub Actions for unit tests.",
                "category": "DevOps"
            }
        ]
        ```"""
        tasks = DocumentationAgent._parse_tasks(raw)
        assert len(tasks) == 2
        assert tasks[0].priority == "P0"
        assert tasks[0].category == "Security"
        assert tasks[1].priority == "P1"


# ════════════════════════════════════════════════════════════════
# 5. REPORT BUILDER & PIPELINE COMPILATION
# ════════════════════════════════════════════════════════════════

class TestReportBuilder:
    """Tests for full report markdown synthesis."""

    def test_build_full_report_structure(self):
        meta = RepoMetadata(
            name="test-repo",
            full_name="user/test-repo",
            language="Python",
            stars=120,
            forks=15,
            html_url="https://github.com/user/test-repo",
        )
        plan = "1. Audit dependencies\n2. Inspect endpoints"
        findings = [
            SecurityFinding(
                severity="HIGH",
                title="Hardcoded Secret",
                description="API key in plain text.",
                file_path="config.py",
                recommendation="Use env vars.",
            )
        ]
        sec_summary = "1 high risk issue found."
        architecture = "### System Overview\nMicroservice design."
        readme = "# test-repo\nGenerated README."
        tasks = [
            TaskItem(
                priority="P0",
                title="Rotate secret",
                description="Immediately revoke compromised key.",
                category="Security",
            )
        ]
        decisions = [
            AgentDecision(
                agent="OrchestratorAgent",
                action="Prioritized security scan",
                reasoning="User requested security audit.",
            )
        ]

        report = build_full_report(
            meta, 85, plan, findings, sec_summary,
            architecture, readme, tasks, decisions
        )

        assert "# DevPulse AI — Full Audit Report" in report
        assert "user/test-repo" in report
        assert "Health Score:** 85/100" in report
        assert "Hardcoded Secret" in report
        assert "Rotate secret" in report
        assert "OrchestratorAgent" in report


# ════════════════════════════════════════════════════════════════
# 6. MOCKED AGENT PIPELINE INTEGRATION
# ════════════════════════════════════════════════════════════════

class TestMockedAgentExecution:
    """Tests the agent methods using mocked Gemini client calls."""

    @patch.object(OrchestratorAgent, "_call")
    def test_orchestrator_planning(self, mock_call):
        mock_call.return_value = "1. GitHub inspection\n2. Security analysis\n3. Architecture synthesis"
        agent = OrchestratorAgent(api_key="fake-key-for-test")
        meta = RepoMetadata(name="demo", full_name="demo/demo", language="Python")
        tree = [TreeEntry(path="app.py", type="blob", size=100)]

        plan = agent.plan("Audit security", meta, tree)

        assert "1. GitHub inspection" in plan
        assert len(agent.decisions) == 1
        assert agent.decisions[0].action == "Generated workflow plan"

    @patch.object(CodeSecurityAuditorAgent, "_call")
    def test_auditor_audit(self, mock_call):
        mock_call.return_value = '{"summary": "Clean", "findings": []}'
        agent = CodeSecurityAuditorAgent(api_key="fake-key-for-test")
        meta = RepoMetadata(name="demo", full_name="demo/demo", language="Python")
        files = [RepoFile(path="app.py", content="print('hello')", size=14)]

        findings, summary = agent.audit(files, meta, "Audit code", "plan")

        assert findings == []
        assert summary == "Clean"
        assert len(agent.decisions) == 1
