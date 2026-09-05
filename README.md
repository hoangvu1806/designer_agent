# Agentic Designer V2
# Agentic Designer

Greenfield source for one deliberate workflow:
AI-powered UI/UX design workflow assistant connecting **Google ADK (Agent Development Kit)** and **OpenPencil** via **MCP (Model Context Protocol)**.

```text
Natural request → structured UI specification → human review
→ real OpenPencil components → content binding → independent `.fig` file
→ layout check → final review
Natural Language Request → Structured UI Specification (LLM) → Human Review (Checkpoint 1)
  → Design System Component Discovery & Binding → JSX Assembly & OpenPencil Vector Render
  → Layout QA Review (Deterministic + Semantic) → Final Human Review (Checkpoint 2) → .fig Artifact
```

The Design System file is read as a component source. A run creates or updates a
separate `.fig` file, so generated screens can be versioned and shared independently.
---

## Source layout
## 🌟 Key Features

- `backend/` — FastAPI, SQLite checkpoints, Google ADK 2.x with its LiteLLM model connector.
- `frontend/` — React, Vite, TypeScript, SSE workflow UI and browser-owned MCP settings.
- `infra/` — OpenPencil MCP runtime notes; nothing starts automatically.
- `docs/` — architecture and implementation status.
- **Google ADK & Structured JSON Engine**: Uses Google Agent Development Kit (`google-adk`) with LiteLLM to guarantee 100% schema-compliant outputs (`UiSpecification`, `ComponentBindingSet`, `LayoutReview`).
- **Human-In-The-Loop (HITL)**: Two-phase review gates ensure full user control before code binding and before finalizing canvas designs.
- **Component Binding**: Automatically matches semantic requirements to real design system components (Shadcn UI, Material UI, etc.).
- **OpenPencil MCP Integration**: Full vector rendering, instance cloning, stock photo replacement, and screenshot capture via Model Context Protocol.
- **Docker Ready**: Preconfigured with `Dockerfile` for backend and frontend, and `docker-compose.yml` for single-command deployment.

Offline component knowledge is indexed in
[`docs/knowledge/README.md`](docs/knowledge/README.md). Read its small library guide
and filtered catalog before doing live MCP discovery.
---

Select `shadcn/ui`, `TapTap`, or auto-detection in UI Settings. The backend filters
the matching local knowledge catalog first, verifies the shortlist against live MCP
metadata, and only then allows the LLM to resolve exact IDs, variants, and text slots.
## 📁 Repository Structure

Backend/runtime configuration lives in the root `.env`. Start from `.env.example`;
do not commit real keys. ADK receives `LiteLlm` directly with `LLM_MODEL`, `API_KEY`,
and `BASE_URL`; the key stays in the backend. OpenPencil endpoint, source file,
output file, creation mode, and knowledge catalog belong exclusively to the frontend
Settings panel and are snapshotted into each design run.
```text
designer_agent/
├── backend/               # FastAPI, SQLite, Google ADK 2.x, MCP Client, Prompts
│   ├── app/               # Core application logic, routers, JSX compiler, OpenPencil gateway
│   ├── prompts/           # Specialized Agent prompts (router, analyzer, resolver, etc.)
│   ├── tests/             # Backend test suites (pytest)
│   ├── Dockerfile         # Production Python 3.11 container
│   ├── requirements.txt   # Backend dependencies
│   └── run.py             # Local development server entrypoint
├── frontend/              # React 18, Vite, TypeScript, TailwindCSS, Lucide icons
│   ├── src/               # UI components, SSE streaming client, review panels
│   ├── Dockerfile         # Multi-stage Node builder + Nginx production container
│   └── nginx.conf         # Reverse-proxy configuration for API & SSE streaming
├── docs/                  # Architecture documentation and knowledge base
├── .dockerignore          # Docker build exclusions
├── .env.example           # Template for environment variables (safe to commit)
├── .gitignore             # Comprehensive Git exclusion rules (protects .env & secrets)
└── docker-compose.yml     # Container orchestration for backend & frontend
```

## Run locally
---

Use the existing Python environment; this repository does not install packages.
## 🚀 Getting Started

```powershell
cd E:\working\BA\designer_agent
Copy-Item .env.example .env
### 1. Prerequisites

- Docker & Docker Compose (for containerized deployment)
- *Or* Python 3.11+ & Node.js 20+ (for local development)
- OpenPencil running with MCP enabled (default `http://localhost:7600/mcp`)

### 2. Environment Configuration

Copy `.env.example` to `.env` and provide your API keys:

```bash
cp .env.example .env
```

> [!CAUTION]
> **Security Notice**: Never commit your `.env` file or API keys to version control. The `.gitignore` file is configured to prevent committing `.env` and runtime data.

Key configuration variables:
```ini
BACKEND_PORT=8282
FRONTEND_PORT=3232
DATABASE_URL=sqlite:///./data/designer_agent.db
CORS_ORIGINS=http://localhost:3232,http://127.0.0.1:3232
VITE_API_BASE_URL=http://127.0.0.1:8282/api/v1

# LLM Configuration
LLM_MODEL=gemini/gemini-2.5-flash
API_KEY=your-api-key-here
BASE_URL=https://litellm.imespro.ai/

# OpenPencil MCP Settings
MCP_TIMEOUT_SECONDS=150
OPENPENCIL_PORT=1420
OPENPENCIL_MCP_PORT=7600
```

---

## 🐳 Running with Docker (Recommended for VPS)

To build and run both Backend and Frontend:

```bash
docker compose up -d --build
```

- **Frontend UI**: `http://<YOUR_IP>:3232`
- **Backend API**: `http://<YOUR_IP>:8282`
- **Swagger Docs**: `http://<YOUR_IP>:8282/api/docs`

To view logs:
```bash
docker compose logs -f
```

To stop containers:
```bash
docker compose down
```

---

## 💻 Local Development

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

In another terminal:

```powershell
cd E:\working\BA\designer_agent\frontend
### Frontend
```bash
cd frontend
npm install
npm run dev
```

Ports in `.env.example`:
---

- UI: `http://127.0.0.1:3232`
- API: `http://127.0.0.1:8282/api/v1`
- OpenAPI: `http://127.0.0.1:8282/api/docs`
## 🧪 Testing

The first vertical slice works without OpenPencil: it creates sessions, streams state,
generates a structured specification, renders a semantic preview, and waits for
Review 1. File assembly continues only with a real OpenPencil MCP context; metadata is never faked.
Run backend tests:
```bash
pytest backend/tests
```

After assembly, the workbench shows the saved `.fig` artifact and measured layout
findings. Final approval is disabled while deterministic checks report missing
instances/placeholders, major overlap, or viewport overflow. Retry resumes a failed
MCP section without creating a new run; request changes creates a controlled revision.
Build frontend check:
```bash
cd frontend && npm run build
```

## OpenPencil
---

Set `OPENPENCIL_MCP_AUTH_TOKEN` in `.env`, start the OpenPencil MCP runtime, then
enter its endpoint plus source/output paths in the UI Settings panel. The backend has
no MCP endpoint or file-path fallback. Paths must stay inside the root configured on
the OpenPencil process. See `docs/OPENPENCIL_DECISION.md` for the runtime model.
## 📄 License

MIT License.
