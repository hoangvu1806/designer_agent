# Implementation status

## Implemented

- FastAPI v1 routes, typed errors, SQLite checkpoints, reviews, and replayable SSE.
- Google ADK 2.x workflow with the direct `LiteLlm` model connector.
- Structured analysis, component resolution, revision, and layout-review prompts.
- Progressive component knowledge routing for the generated shadcn/ui and TapTap
  catalogs; only a small requirement-specific shortlist reaches the resolver.
- React/Vite workbench with sessions, horizontal state rail, chat, preview, JSON,
  two human review gates, artifact/layout findings, retry/cancel controls, and a
  browser-owned OpenPencil file profile.
- The state rail follows the latest design workflow in the session, preserves the
  actual failed/blocked stage, fits the available width, and ignores ordinary chat
  runs.
- OpenPencil HTTP MCP handshake and capability discovery with backend-only auth.
- Source-file component discovery, independent output-file creation, JSX rendering,
  exact real-instance/text-slot binding, geometry and overlap capture, save, and
  guarded final review.
- Versioned artifact endpoint, deterministic binding/viewport/placeholder/overlap/
  touch-target checks, semantic LLM layout review, and controlled revision prompts.
- Approve and retry refresh the complete MCP profile from current frontend settings.
  No endpoint or source/output fallback exists in backend or frontend code; nested MCP
  TaskGroup errors are unwrapped into actionable file/tool errors.

## Deliberate limitations

- The OpenPencil runtime must be running for MCP writes; only the CLI is fully headless.
- Stable cross-document published libraries are not assumed. The current strategy
  copies the source to output before creating a generated page.
- A browser-share URL is not synthesized for local files. The saved output path,
  document ID, page ID, and root node ID are returned; external sharing requires a
  deployment-specific storage or hosting adapter.
- No package installation, Docker startup, or external server startup is performed by
  this repository.
