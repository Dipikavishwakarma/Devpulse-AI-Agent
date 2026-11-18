"""
DevPulse AI — Streamlit Application
=====================================
Autonomous GitHub Repo & Workflow Agent
Prompt War – 24-Hour AI Hackathon  |  Theme 1: Automation
"""

import os
import time

import streamlit as st
from dotenv import load_dotenv

from agents import (
    DEMO_REPO_URL,
    AgentDecision,
    BaseAgent,
    CodeSecurityAuditorAgent,
    DocumentationAgent,
    GitHubTool,
    GitHubToolError,
    OrchestratorAgent,
    RateLimitError,
    build_full_report,
)

load_dotenv()

# ════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="DevPulse AI — GitHub Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════
#  CUSTOM CSS
# ════════════════════════════════════════════════════════════════

st.markdown("""
<style>
/* ── Global ────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #0a0e17;
}

/* ── Header ────────────────────────────────────────────────── */
.hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, #4f8ff7 0%, #a855f7 50%, #06d6a0 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0;
    letter-spacing: -0.5px;
}
.hero-sub {
    color: #8b95a5;
    font-size: 1.05rem;
    margin-top: 2px;
    margin-bottom: 24px;
}

/* ── Metric cards ──────────────────────────────────────────── */
.metric-card {
    background: linear-gradient(145deg, #141a2a 0%, #0f1320 100%);
    border: 1px solid #2d3748;
    border-radius: 14px;
    padding: 22px 18px;
    text-align: center;
    transition: border-color 0.25s, box-shadow 0.25s;
}
.metric-card:hover, .metric-card:focus {
    border-color: #4f8ff7;
    outline: 2px solid #4f8ff7;
    outline-offset: 2px;
}
.metric-icon {
    font-size: 1.6rem;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.1;
}
.metric-value.score-green  { color: #00e676; }
.metric-value.score-yellow { color: #ffd166; }
.metric-value.score-red    { color: #ff5252; }
.metric-label {
    font-size: 0.8rem;
    color: #cbd5e1;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    margin-top: 6px;
}

/* ── Badges with WCAG High Contrast ────────────────────────── */
.badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-right: 6px;
}
.badge-high   { background: #b71c1c; color: #ffffff; border: 1px solid #ef5350; }
.badge-medium { background: #e65100; color: #ffffff; border: 1px solid #ff9800; }
.badge-low    { background: #1b5e20; color: #ffffff; border: 1px solid #4caf50; }
.badge-p0     { background: #b71c1c; color: #ffffff; border: 1px solid #ef5350; }
.badge-p1     { background: #e65100; color: #ffffff; border: 1px solid #ff9800; }
.badge-p2     { background: #0d47a1; color: #ffffff; border: 1px solid #42a5f5; }

/* ── Finding card ──────────────────────────────────────────── */
.finding-card {
    background: #111827;
    border-left: 5px solid #475569;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 14px;
    transition: outline 0.2s;
}
.finding-card:focus {
    outline: 2px solid #4f8ff7;
    outline-offset: 2px;
}
.finding-card.sev-HIGH   { border-left-color: #ef5350; }
.finding-card.sev-MEDIUM { border-left-color: #ff9800; }
.finding-card.sev-LOW    { border-left-color: #4caf50; }
.finding-title {
    font-weight: 700;
    color: #f8fafc;
    font-size: 1.05rem;
    margin-bottom: 6px;
}
.finding-meta {
    font-size: 0.85rem;
    color: #94a3b8;
    margin-bottom: 6px;
}
.finding-meta code {
    color: #e2e8f0;
    background: #1e293b;
    padding: 2px 6px;
    border-radius: 4px;
}
.finding-desc {
    color: #cbd5e1;
    font-size: 0.92rem;
    line-height: 1.5;
    margin: 8px 0;
}
.finding-rec {
    color: #38ef7d;
    font-size: 0.9rem;
    line-height: 1.4;
    background: #064e3b33;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid #05966944;
}

/* ── Task card ─────────────────────────────────────────────── */
.task-card {
    background: #111827;
    border: 1px solid #2d3748;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
    transition: outline 0.2s;
}
.task-card:focus {
    outline: 2px solid #4f8ff7;
    outline-offset: 2px;
}
.task-title {
    font-weight: 700;
    color: #f8fafc;
    font-size: 0.98rem;
}
.task-desc {
    color: #cbd5e1;
    font-size: 0.9rem;
    line-height: 1.45;
    margin-top: 6px;
}
.task-cat {
    display: inline-block;
    background: #1e293b;
    color: #93c5fd;
    border: 1px solid #3b82f644;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.74rem;
    font-weight: 600;
    margin-left: 8px;
}

/* ── Decision log ──────────────────────────────────────────── */
.decision-entry {
    background: #0f172a;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
    font-size: 0.88rem;
    transition: outline 0.2s;
}
.decision-entry:focus {
    outline: 2px solid #a855f7;
    outline-offset: 2px;
}
.decision-agent {
    color: #c084fc;
    font-weight: 700;
}
.decision-action {
    color: #f8fafc;
    font-weight: 600;
}
.decision-reason {
    color: #cbd5e1;
    display: inline-block;
    margin-top: 4px;
    font-size: 0.84rem;
}

/* ── Sidebar polish ────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: #0d1120;
    border-right: 1px solid #1e2740;
}

/* ── Status containers ─────────────────────────────────────── */
div[data-testid="stStatusWidget"] {
    background: #111827;
    border-radius: 10px;
}

/* ── Tab labels ────────────────────────────────────────────── */
button[data-baseweb="tab"] {
    font-weight: 600;
}

/* ── Fallback banner ───────────────────────────────────────── */
.fallback-banner {
    background: #2a1b04;
    border: 1px solid #f59e0b;
    border-radius: 10px;
    padding: 12px 18px;
    color: #fef3c7;
    font-size: 0.92rem;
    line-height: 1.45;
    margin-bottom: 18px;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
#  HEADER
# ════════════════════════════════════════════════════════════════

st.markdown(
    """
    <header role="banner" aria-label="DevPulse AI Application Header">
        <h1 class="hero-title" style="margin-top:0;">⚡ DevPulse AI</h1>
        <p class="hero-sub">Autonomous GitHub Repo & Workflow Agent — powered by multi-agent Gemini intelligence</p>
    </header>
    """,
    unsafe_allow_html=True,
)

# ════════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### ⚙️ Pipeline Configuration")

    # ── API key ───────────────────────────────────────────────
    env_key = os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input(
        "🔑 Google Gemini API Key",
        value=env_key,
        type="password",
        placeholder="AIzaSy...",
        help="Required: Gemini API Key (starts with AIzaSy...). Get free keys from https://aistudio.google.com/apikey. Stored strictly in-memory during this session.",
    )

    st.divider()

    # ── Repo URL ──────────────────────────────────────────────
    def _load_demo():
        st.session_state["repo_url_input"] = DEMO_REPO_URL

    repo_url = st.text_input(
        "🔗 Public GitHub Repository URL",
        placeholder="https://github.com/owner/repo",
        key="repo_url_input",
        help="Enter any public GitHub repository URL (e.g., https://github.com/tiangolo/fastapi) or shorthand (e.g., pallets/flask). No personal access token required.",
    )
    st.button(
        "📦 Load Demo Repo (FastAPI)",
        on_click=_load_demo,
        use_container_width=True,
        help="Pre-fills the URL field with the popular FastAPI repository for an instant live demonstration.",
    )

    st.divider()

    # ── User goal ─────────────────────────────────────────────
    user_goal = st.text_area(
        "🎯 Analysis Goal / Custom Instruction",
        value="Audit for security vulnerabilities, analyse architecture, and generate setup documentation.",
        height=100,
        help="Direct the Orchestrator Agent on what to prioritize (e.g., deep security audit, architectural diagram, or quick developer onboarding docs).",
    )

    st.divider()

    # ── Run button ────────────────────────────────────
    run_clicked = st.button(
        "🚀 Run DevPulse Analysis",
        type="primary",
        use_container_width=True,
        disabled=not api_key,
        help="Executes the full 4-agent autonomous pipeline: GitHub data fetching, workflow planning, code security audit, and documentation synthesis.",
    )
    if not api_key:
        st.caption("⬆️ Enter your Gemini API key above to enable analysis.")

    st.divider()
    st.caption(
        "Built for **Prompt War — 24-Hour AI Hackathon**  \n"
        "Theme 1: Automation — Intelligent AI Agents"
    )


# ════════════════════════════════════════════════════════════════
#  HELPERS (ACCESSIBLE ARIA RENDERING)
# ════════════════════════════════════════════════════════════════

def _score_class(score: int) -> str:
    if score >= 70:
        return "score-green"
    if score >= 45:
        return "score-yellow"
    return "score-red"


def _metric_card(icon: str, value: str, label: str,
                 extra_class: str = "") -> str:
    return (
        f'<div class="metric-card" role="region" aria-label="{label}: {value}" tabindex="0">'
        f'<div class="metric-icon" aria-hidden="true">{icon}</div>'
        f'<div class="metric-value {extra_class}" aria-live="polite">{value}</div>'
        f'<div class="metric-label">{label}</div>'
        f'</div>'
    )


def _render_finding(f) -> str:
    sev_cls = f"badge-{f.severity.lower()}"
    return (
        f'<article class="finding-card sev-{f.severity}" role="article" '
        f'aria-label="Security finding: {f.title}, Severity: {f.severity}" tabindex="0">'
        f'<div class="finding-title">'
        f'<span class="badge {sev_cls}" role="status" aria-label="Severity level: {f.severity}">{f.severity}</span> {f.title}</div>'
        f'<div class="finding-meta" aria-label="Affected file path: {f.file_path}">📄 <code>{f.file_path}</code></div>'
        f'<div class="finding-desc">{f.description}</div>'
        f'<div class="finding-rec" aria-label="Remediation guidance: {f.recommendation}">💡 <strong>Remediation:</strong> {f.recommendation}</div>'
        f'</article>'
    )


def _render_task(t) -> str:
    pri_cls = f"badge-{t.priority.lower()}"
    return (
        f'<div class="task-card" role="listitem" '
        f'aria-label="Task: {t.title}, Priority: {t.priority}, Category: {t.category}" tabindex="0">'
        f'<div class="task-title">'
        f'<span class="badge {pri_cls}" role="status" aria-label="Priority: {t.priority}">{t.priority}</span> {t.title}'
        f'<span class="task-cat" aria-label="Category: {t.category}">{t.category}</span></div>'
        f'<div class="task-desc">{t.description}</div>'
        f'</div>'
    )


def _render_decision(d) -> str:
    return (
        f'<div class="decision-entry" role="listitem" '
        f'aria-label="Agent {d.agent} decision: {d.action}" tabindex="0">'
        f'<span class="decision-agent">🤖 {d.agent}</span> → '
        f'<span class="decision-action">{d.action}</span><br>'
        f'<span class="decision-reason" aria-label="Reasoning: {d.reasoning}"><em>Reasoning:</em> {d.reasoning}</span>'
        f'</div>'
    )


# ════════════════════════════════════════════════════════════════
#  PIPELINE EXECUTION
# ════════════════════════════════════════════════════════════════

if run_clicked:
    if not repo_url.strip():
        st.error("Please enter a GitHub repository URL or click **Load Demo Repo**.")
        st.stop()

    decisions: list[AgentDecision] = []
    is_fallback = False
    t_start = time.time()

    # ── Step 1: GitHub Tool Agent ─────────────────────────────
    with st.status(
        "🔗 **GitHub Tool Agent** — Fetching live repo data…",
        expanded=True,
    ) as status_gh:
        st.write("Parsing GitHub URL…")
        tool = GitHubTool()
        try:
            owner, repo_name = tool.parse_url(repo_url)
            st.write(f"Target: `{owner}/{repo_name}`")
        except GitHubToolError as exc:
            st.error(str(exc))
            st.stop()

        try:
            st.write("📡 Fetching repository metadata…")
            metadata = tool.fetch_metadata(owner, repo_name)
            st.write(f"✓ **{metadata.full_name}** — ⭐ {metadata.stars:,}")

            st.write("🌳 Fetching file tree…")
            tree = tool.fetch_tree(owner, repo_name, metadata.default_branch)
            blob_count = sum(1 for e in tree if e.type == "blob")
            st.write(f"✓ {len(tree)} entries ({blob_count} files)")

            st.write("📂 Selecting & downloading key source files…")
            files = tool.fetch_key_files(
                owner, repo_name, tree, metadata.default_branch
            )
            total_bytes = sum(f.size for f in files)
            st.write(f"✓ Fetched **{len(files)}** files ({total_bytes:,} bytes)")

        except RateLimitError:
            st.warning(
                "⚠️ GitHub API rate limit hit — switching to **fallback demo data** "
                "so the demo continues smoothly."
            )
            metadata, tree, files = tool.get_demo_fallback()
            is_fallback = True

        except GitHubToolError as exc:
            st.error(f"GitHub API error: {exc}")
            st.stop()

        health_score, health_bk = tool.compute_health_score(metadata, tree, files)
        decisions.append(AgentDecision(
            agent="GitHub Tool",
            action=f"Fetched {len(tree)} tree entries, downloaded {len(files)} key files",
            reasoning="Selected files by importance patterns (config, entry-point, CI, deps).",
        ))
        status_gh.update(
            label="✅ **GitHub Tool Agent** — Data fetched",
            state="complete",
        )

    # ── Step 2: Orchestrator Agent ────────────────────────────
    with st.status(
        "🧠 **Orchestrator Agent** — Interpreting goal & planning workflow…",
        expanded=True,
    ) as status_orch:
        st.write(f'Analysing user goal: *"{user_goal[:90]}…"*')
        orchestrator = OrchestratorAgent(api_key)
        plan = orchestrator.plan(user_goal, metadata, tree)
        st.write("✓ Workflow plan generated")
        st.markdown(plan[:600] + ("…" if len(plan) > 600 else ""))
        decisions.extend(orchestrator.decisions)
        status_orch.update(
            label="✅ **Orchestrator Agent** — Workflow planned",
            state="complete",
        )

    # ── Step 3: Code & Security Auditor ───────────────────────
    with st.status(
        "🔒 **Code & Security Auditor** — Scanning for vulnerabilities…",
        expanded=True,
    ) as status_sec:
        st.write(f"Analysing {len(files)} source files…")
        auditor = CodeSecurityAuditorAgent(api_key)
        findings, sec_summary = auditor.audit(files, metadata, user_goal, plan)
        n_h = sum(1 for f in findings if f.severity == "HIGH")
        n_m = sum(1 for f in findings if f.severity == "MEDIUM")
        n_l = sum(1 for f in findings if f.severity == "LOW")
        st.write(f"✓ Scan complete — **{len(findings)}** findings "
                 f"(🔴 {n_h} High · 🟡 {n_m} Medium · 🟢 {n_l} Low)")
        decisions.extend(auditor.decisions)
        status_sec.update(
            label="✅ **Security Auditor** — Scan complete",
            state="complete",
        )

    # ── Step 4: Documentation & Action Planner ────────────────
    with st.status(
        "📝 **Documentation Agent** — Generating docs & task list…",
        expanded=True,
    ) as status_doc:
        doc_agent = DocumentationAgent(api_key)

        st.write("Writing architecture document…")
        architecture = doc_agent.generate_architecture(
            files, metadata, tree, sec_summary
        )

        st.write("Generating README.md…")
        readme = doc_agent.generate_readme(metadata, architecture, findings)

        st.write("Building prioritised task checklist…")
        tasks = doc_agent.generate_tasks(findings, architecture, user_goal, metadata)
        st.write(f"✓ Generated architecture doc, README, and **{len(tasks)}** tasks")

        decisions.extend(doc_agent.decisions)
        status_doc.update(
            label="✅ **Documentation Agent** — Docs generated",
            state="complete",
        )

    elapsed = time.time() - t_start

    # ── Build full report ─────────────────────────────────────
    full_report = build_full_report(
        metadata, health_score, plan, findings, sec_summary,
        architecture, readme, tasks, decisions,
    )

    # ── Persist results ───────────────────────────────────────
    st.session_state["results"] = {
        "metadata": metadata,
        "health_score": health_score,
        "health_bk": health_bk,
        "tree": tree,
        "files": files,
        "plan": plan,
        "findings": findings,
        "sec_summary": sec_summary,
        "architecture": architecture,
        "readme": readme,
        "tasks": tasks,
        "decisions": decisions,
        "full_report": full_report,
        "is_fallback": is_fallback,
        "elapsed": elapsed,
    }


# ════════════════════════════════════════════════════════════════
#  RESULTS DASHBOARD
# ════════════════════════════════════════════════════════════════

if "results" in st.session_state:
    r = st.session_state["results"]
    meta = r["metadata"]

    st.markdown("---")

    # ── Fallback banner ───────────────────────────────────────
    if r["is_fallback"]:
        st.markdown(
            '<div class="fallback-banner" role="alert" aria-live="assertive">'
            '⚠️ <strong>Fallback Mode Active:</strong> Showing cached demo data because the GitHub API rate limit was '
            'reached. All multi-agent analysis is still executing live via Google Gemini.</div>',
            unsafe_allow_html=True,
        )

    # ── Metric cards ──────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(
            _metric_card("💚", f'{r["health_score"]}', "Health Score",
                         _score_class(r["health_score"])),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _metric_card("💻", meta.language, "Primary Lang"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _metric_card("⭐", f'{meta.stars:,}', "Stars"),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            _metric_card("🍴", f'{meta.forks:,}', "Forks"),
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            _metric_card("⏱️", f'{r["elapsed"]:.1f}s', "Analysis Time"),
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Agent Decision Log ────────────────────────────────────
    with st.expander("🤖 **Agent Decision Log** — Why the agents chose each step", expanded=False):
        for d in r["decisions"]:
            st.markdown(_render_decision(d), unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔒 Security & Bug Audit",
        "📐 Architecture & README",
        "✅ Task Checklist",
        "📋 Orchestrator Plan",
    ])

    # ── Tab 1: Security Audit ─────────────────────────────────
    with tab1:
        st.markdown("#### Executive Summary")
        st.info(r["sec_summary"] if r["sec_summary"] else "No summary available.")
        st.markdown("#### Findings")
        if r["findings"]:
            # Summary badges
            n_h = sum(1 for f in r["findings"] if f.severity == "HIGH")
            n_m = sum(1 for f in r["findings"] if f.severity == "MEDIUM")
            n_l = sum(1 for f in r["findings"] if f.severity == "LOW")
            st.markdown(
                f'<span class="badge badge-high">{n_h} HIGH</span>'
                f'<span class="badge badge-medium">{n_m} MEDIUM</span>'
                f'<span class="badge badge-low">{n_l} LOW</span>',
                unsafe_allow_html=True,
            )
            st.markdown("")
            for f in r["findings"]:
                st.markdown(_render_finding(f), unsafe_allow_html=True)
        else:
            st.success("No security issues detected — nice! 🎉")

    # ── Tab 2: Architecture & README ──────────────────────────
    with tab2:
        sub1, sub2 = st.tabs(["📐 Architecture Document", "📄 Generated README.md"])
        with sub1:
            st.markdown(r["architecture"])
        with sub2:
            st.markdown(r["readme"])

    # ── Tab 3: Task Checklist ─────────────────────────────────
    with tab3:
        st.markdown("#### Prioritised Task Backlog")
        if r["tasks"]:
            for t in r["tasks"]:
                st.markdown(_render_task(t), unsafe_allow_html=True)
        else:
            st.info("No tasks generated.")

    # ── Tab 4: Orchestrator Plan ──────────────────────────────
    with tab4:
        st.markdown("#### Workflow Plan")
        st.markdown(r["plan"])

    # ── Download report ───────────────────────────────────────
    st.markdown("---")
    st.download_button(
        "📥 Download Full Audit Report (.md)",
        data=r["full_report"],
        file_name=f"devpulse_report_{meta.name}.md",
        mime="text/markdown",
        use_container_width=True,
        help="Download the complete Markdown audit report containing security findings, architecture documentation, generated README, and prioritized tasks.",
    )

else:
    # ── Empty state ───────────────────────────────────────────
    st.markdown("---")
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.markdown(
            """
            <div role="status" aria-label="Awaiting repository analysis input" style="text-align:center; padding: 60px 20px;">
                <div style="font-size: 3.5rem; margin-bottom: 12px;" aria-hidden="true">🚀</div>
                <h2 style="color:#f8fafc; font-size:1.5rem; font-weight:700; margin-bottom:8px;">
                    Ready to Analyse
                </h2>
                <p style="color:#cbd5e1; font-size:0.95rem; line-height:1.5; max-width:440px; margin:auto;">
                    Paste any public GitHub repo URL in the sidebar,
                    describe your custom instruction, and click
                    <strong style="color:#4f8ff7;">Run DevPulse Analysis</strong>
                    to launch the autonomous multi-agent pipeline.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
