<div align="center">

# ⚡ DevPulse AI

### Autonomous GitHub Repo & Workflow Agent

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Gemini](https://img.shields.io/badge/Google_Gemini-2.0_Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*Paste any public GitHub URL → get a full security audit, architecture docs, and prioritised task backlog — powered by a multi-agent Gemini pipeline.*

</div>

---

live Url- https://dipikavishwakarma-devpulse-ai-agent-app-orocpy.streamlit.app/

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Problem Statement](#-problem-statement)
- [Solution Architecture](#-solution-architecture)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Local Setup](#-local-setup)
- [Deployment — Streamlit Cloud](#-deployment--streamlit-cloud)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Hackathon Info](#-hackathon-info)

---

## 🎯 Project Overview

**DevPulse AI** is an autonomous multi-agent system that analyses any public GitHub repository in real time. It fetches live data from the GitHub REST API, runs four specialised AI agents powered by Google Gemini, and produces:

1. A **Security & Bug Audit** with severity-tagged findings and exact file references.
2. An **Architecture Document & auto-generated README.md**.
3. A **Prioritised Task Checklist** (P0 → P2) so developers know exactly what to fix first.

All decisions are logged and displayed so judges (and users) can see *why* each agent took each step.

---

## 🔍 Problem Statement

Developers and teams frequently need to:
- Quickly evaluate an unfamiliar open-source repository for security risks.
- Understand a project's architecture without reading every file.
- Generate onboarding documentation and a backlog of improvements.

Doing this manually takes hours. **DevPulse AI automates the entire workflow in under 60 seconds** using coordinated AI agents.

---

## 🏗️ Solution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit UI (app.py)                    │
│   ┌───────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│   │  Sidebar   │  │  Dashboard   │  │   Tabbed Results      │   │
│   │  API Key   │  │  Metrics     │  │   • Security Audit    │   │
│   │  Repo URL  │  │  Health Bar  │  │   • Architecture/README│  │
│   │  Goal Box  │  │  Dec. Log    │  │   • Task Checklist    │   │
│   └───────────┘  └──────────────┘  └───────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   agents.py (Pipeline)  │
              └────────────┬────────────┘
        ┌──────────┬───────┴───────┬──────────────┐
        ▼          ▼               ▼              ▼
  ┌──────────┐ ┌───────────┐ ┌──────────────┐ ┌──────────────┐
  │ GitHub   │ │Orchestrator│ │ Security     │ │Documentation │
  │ Tool     │ │  Agent     │ │ Auditor Agent│ │   Agent      │
  │ Agent    │ │ (Gemini)   │ │  (Gemini)    │ │  (Gemini)    │
  └────┬─────┘ └───────────┘ └──────────────┘ └──────────────┘
       │
       ▼
  GitHub REST API
  (unauthenticated)
```

**Pipeline flow:**
1. **GitHub Tool Agent** → Fetches repo metadata, file tree, and key source files via the GitHub REST API.
2. **Orchestrator Agent** → Interprets the user's goal and plans which analyses to prioritise.
3. **Code & Security Auditor** → Scans fetched files for vulnerabilities, bugs, and anti-patterns.
4. **Documentation Agent** → Generates architecture docs, README.md, and a prioritised task checklist.

If the GitHub API rate limit is hit, the system automatically falls back to cached demo data so the **live demo never fails**.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔗 **Live GitHub Integration** | Fetches real repo data — no token required for public repos |
| 🎯 **Custom Goal Input** | User describes what to focus on; the Orchestrator adapts autonomously |
| 🧠 **4-Agent Pipeline** | Orchestrator → GitHub Tool → Security Auditor → Documentation Agent |
| 📊 **Health Score** | 0–100 score based on README, CI/CD, tests, license, deps, Docker, etc. |
| 🔒 **Security Audit** | HIGH / MEDIUM / LOW findings with file paths and fix recommendations |
| 📐 **Auto Architecture Docs** | Component breakdown, tech stack, data flow analysis |
| 📄 **README Generator** | Polished README.md with badges, quick-start, and structure |
| ✅ **Task Checklist** | P0–P2 prioritised backlog with categories |
| 🤖 **Decision Log** | Full transparency — see *why* each agent chose each step |
| 📥 **One-Click Download** | Export the full audit as a `.md` report |
| 🌙 **Dark-Mode UI** | Executive-quality dashboard with custom CSS cards and badges |
| 🛡️ **Fallback Mode** | Demo never fails — cached data activates on rate limits |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit 1.30+ (custom CSS, `st.status()`, tabs, columns) |
| **AI Engine** | Google Gemini 2.0 Flash via `google-genai` SDK |
| **External Tool** | GitHub REST API v3 (unauthenticated — public repos) |
| **Language** | Python 3.10+ |
| **Config** | `python-dotenv` for `.env` secrets |
| **HTTP** | `requests` library |

---

## 🚀 Local Setup

### Prerequisites
- Python 3.10 or later
- A [Google Gemini API key](https://aistudio.google.com/apikey) (free tier works)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/devpulse-ai.git
cd devpulse-ai

# 2. Create a virtual environment (recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key (pick one method)
#    Method A — .env file:
cp .env.example .env
#    Edit .env and paste your key
#    Method B — enter it in the sidebar at runtime

# 5. Launch the app
streamlit run app.py
```

The app opens at **http://localhost:8501**.

---

## ☁️ Deployment — Streamlit Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
3. Select your repo, branch, and set **Main file path** to `app.py`.
4. Under **Advanced settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your-key-here"
   ```
5. Click **Deploy**. Your app will be live in ~2 minutes.

> **Tip:** Streamlit Cloud secrets are injected as environment variables, so `python-dotenv` picks them up automatically.

---

## 📖 Usage

1. **Enter your Gemini API key** in the sidebar (or set it in `.env`).
2. **Paste any public GitHub URL** — or click **📦 Load Demo Repo**.
3. **Describe your goal** (e.g., *"Audit security and generate setup docs"*).
4. Click **🚀 Run DevPulse Analysis**.
5. Watch the agents execute in real time with `st.status()` progress cards.
6. Explore results across tabs: Security Audit · Architecture & README · Task Checklist.
7. Click **📥 Download Full Audit Report** for a comprehensive `.md` file.

---

## 📂 Project Structure

```
devpulse-ai/
├── app.py              # Streamlit UI, pipeline orchestration, dashboard
├── agents.py           # Agent classes, GitHub tool, data models, report builder
├── requirements.txt    # Python dependencies
├── .env.example        # Template for API key configuration
└── README.md           # This file
```

---

## 🏆 Hackathon Info

| | |
|--|--|
| **Event** | Prompt War — 24-Hour AI Hackathon |
| **Theme** | Theme 1: Automation — Build Intelligent AI Agents |
| **Project** | DevPulse AI — Autonomous GitHub Repo & Workflow Agent |
| **Key Criteria Met** | Real external tool interaction (GitHub API), autonomous decision-making (Orchestrator), live multi-agent pipeline with visual progress, executive-quality dashboard UI |

---

## 📄 License

This project is released under the [MIT License](LICENSE).

---

<div align="center">
  <b>Built with ⚡ by DevPulse AI Team</b><br>
  <sub>Powered by Google Gemini & Streamlit</sub>
</div>
