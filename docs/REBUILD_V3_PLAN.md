# Designer Agent V3 — Knowledge-First, OpenPencil-Native Rebuild

> Status: authoritative rebuild plan; no V3 runtime implementation yet.  
> Updated: 2026-09-03.  
> Supersedes the MCP-discovery patches and the headless-compiler/display-only proposal.  
> Core principle: **knowledge routes the agent to a few relevant real components; OpenPencil MCP
> is the tool environment where the agent inspects those components, designs freely, saves, and
> displays the result.**

## 1. Product story

```text
Natural request or normal conversation
→ structured UI specification
→ human structure review
→ retrieve relevant component knowledge
→ inspect a small number of real components through OpenPencil MCP
→ map content into component slots
→ agent designs the complete UI in OpenPencil through MCP
→ inspect and improve the real layout
→ human final review
```

The system must preserve all three goals:

1. **Correctness:** use real components, variants, and editable slots from the selected `.fig`.
2. **Creative flexibility:** the LLM controls composition, hierarchy, art direction, geometry,
   responsive behavior, and when custom primitives are appropriate.
3. **Token efficiency:** knowledge and semantic retrieval prevent the full component catalog,
   raw `.fig`, or full document tree from entering the LLM context.

Normal conversation remains a simple chatbot interaction. It must not create a design workflow,
load component knowledge, call MCP, or change the timeline unless design intent is present.

## 2. Correct mental model

### 2.1. Knowledge is a semantic index, not a replacement for components

Knowledge answers:

- What component families exist?
- What intent, role, and aliases map to each family?
- When should or should not a component be used?
- What variants and semantic slots are expected?
- Which components commonly compose well together?
- Which source file/page/component reference should be inspected?

Knowledge does not contain the entire vector tree, every node, or enough information to recreate
the component visually. It points the agent to the right real component.

### 2.2. Component `.fig` files are the real visual source

The source `.fig` contains the actual:

- appearance and geometry;
- component masters and variants;
- typography, color, effect, and spacing tokens;
- nested components, icons, images, and assets;
- editable text/property/instance slots;
- reference compositions and examples.

After knowledge retrieval produces a shortlist, the agent uses MCP tools to inspect only those
real components and their necessary metadata/rendered appearance. It never needs the entire file
in context.

### 2.3. OpenPencil MCP is the design workspace

OpenPencil MCP is used to:

- open the selected source `.fig` on demand;
- inspect/render shortlisted component samples;
- create or open a separate output document;
- copy/use real components and dependencies;
- create frames, text, images, vectors, and layout containers;
- set properties, variants, content overrides, geometry, and responsive frames;
- inspect bounds and rendered results;
- iterate on the design;
- save the output `.fig`;
- focus/show the result in OpenPencil for human review.

OpenPencil is therefore both the agent's design tool and the user's visual review surface. It is
not merely a viewer for a file designed elsewhere.

## 3. Non-negotiable boundaries

1. Source design-system `.fig` files are immutable.
2. Every run writes to a separate generated output file/page.
3. The LLM never receives raw `.fig` bytes, the full document tree, or all components.
4. Knowledge retrieval happens before MCP component inspection.
5. MCP inspects only shortlisted real components and exact dependencies needed by the design.
6. Knowledge guides selection; live MCP inspection verifies real availability and appearance.
7. The LLM may design freely; knowledge must not force fixed templates or fixed coordinates.
8. Deterministic checks are guardrails, not a replacement layout engine.
9. Component internals are changed only through verified slots/properties or safe instance edits.
10. Workflow state is persisted by the backend and is not inferred from chat cards.
11. MCP connection/document IDs are runtime handles, never durable design-system identities.
12. No source file exceeds 300 lines; target 180–260 lines.

## 4. Data organization

```text
E:/working/BA/designer-data/
  design-systems/                         # immutable real component sources
    Material UI for Figma (and MUI X) (Community).fig
    TapTap Design System丨Developers (Community).fig
    Design System _ v0.3 (Community).fig
    @shadcn_ui - Design System (Community).fig
  generated/                              # outputs created through MCP
    {session_id}/
      {run_id}/
        {screen_slug}.fig
        manifest.json
        preview.png
  cache/                                  # disposable MCP inspection/render cache
```

Versioned knowledge stays in source control:

```text
designer_agent/docs/knowledge/
  README.md
  material-ui.md
  taptap.md
  design-system-v0.3.md
  shadcn-ui.md
```

Each stable `design_system_id` maps to a source path and knowledge file. The backend generates
runtime `document_id` values by opening the source through MCP; those IDs are never persisted as
the source identity.

## 5. Semantic knowledge design

### 5.1. Knowledge entry contract

Each component family entry should contain compact semantic routing data:

```yaml
family: Button
aliases: [cta, action, submit, purchase]
roles: [primary-action, secondary-action, destructive-action]
use_when:
  - Triggering an immediate user action
avoid_when:
  - Navigating through a dense application menu
source:
  file_id: taptap
  page_hint: Button
  component_name_patterns: [Button, Button/*]
variants:
  intent: [primary, secondary, danger]
  size: [small, medium, large]
slots:
  label: text
  leading_icon: instance-swap
  trailing_icon: instance-swap
composition:
  - Use one dominant primary action per visual group
inspection_hints:
  - Render default, disabled, and large states when resolving
```

Exact IDs may be cached as evidence but are always revalidated after a source fingerprint change.

### 5.2. Progressive disclosure

The agent receives context in layers:

```text
Layer 1: design-system identity and foundations
Layer 2: relevant component-family knowledge
Layer 3: small semantic shortlist
Layer 4: exact MCP inspection for finalists only
```

Context rules:

- Normal chat: no design-system context.
- UI specification: foundations and composition guidance only.
- Component resolution: relevant family entries only.
- MCP inspection: at most a small set of finalists per requirement.
- Binding: exact slot/property metadata of chosen components only.
- Layout review: rendered preview and measured findings for affected frames only.

Do not send a complete knowledge file if selected sections are enough. Do not insert full legacy
catalog JSON into prompts. Retrieval is deterministic by roles, aliases, tags, and component
requirements; no vector database is required in the baseline.

### 5.3. Knowledge lifecycle

Knowledge is built or refreshed through an explicit maintenance workflow:

1. Inspect a source `.fig` with MCP/CLI tooling outside a user design run.
2. Group components into semantic families.
3. Record use cases, variants, slots, composition guidance, and source hints.
4. Human-review the knowledge document.
5. Store source fingerprint and knowledge hash.
6. When the source changes, create a drift report instead of silently replacing knowledge.

The existing TapTap and shadcn knowledge are migration inputs. Material UI and Design System
v0.3 knowledge must be created and all four must be reconciled with their current real files.

## 6. Shortlisting and real component inspection

### 6.1. Before MCP

After Review 1, the approved `UiSpecification` contains abstract requirements such as:

```json
{
  "role": "primary-action",
  "intent": "purchase",
  "contentNeeds": ["label", "leading-icon"],
  "visualPriority": "high"
}
```

The knowledge retriever finds relevant families and source hints without reading the entire `.fig`
or calling the LLM with every component.

### 6.2. Through MCP

For shortlisted families, the OpenPencil gateway:

1. opens the source file if it is not already available;
2. locates candidate masters by the knowledge hints;
3. retrieves exact variants, properties, slots, bounds, and dependencies;
4. renders thumbnails/samples when visual comparison is useful;
5. returns a compact normalized candidate summary to the resolver;
6. caches evidence by source fingerprint and component ID.

The resolver sees only the compact finalists and relevant knowledge, then chooses one real
component or explicitly chooses a primitive/custom composition when no component is suitable.

Component use is encouraged where it preserves the design system, but the system must not select
an incorrect component merely to reach 100% reuse.

## 7. Slot mapping — controlled data replacement

Each chosen component gets a verified `ComponentSlotMap`:

```json
{
  "sourceFingerprint": "sha256:...",
  "componentId": "real-component-id",
  "slots": {
    "label": {
      "kind": "text",
      "target": "exact-node-or-property"
    },
    "leadingIcon": {
      "kind": "instance_swap",
      "target": "exact-nested-instance"
    }
  },
  "variantProperties": {
    "size": ["small", "medium", "large"]
  }
}
```

Supported holes:

```text
text
image/fill
icon
variant property
boolean visibility
instance swap
repeated content
content zone / child insertion
```

The agent emits semantic bindings; the MCP execution layer translates them into exact tool calls.
Unverified internal nodes are not edited blindly. If mapping becomes stale, inspect again and ask
for review when remapping is ambiguous.

## 8. Creative design in OpenPencil

### 8.1. What the LLM controls

The agent may decide:

- visual concept and art direction;
- hierarchy and storytelling;
- section composition and ordering;
- whitespace, density, scale, rhythm, and emphasis;
- frames, auto-layout/flex/grid, overlays, and intentional absolute positioning;
- desktop/tablet/mobile behavior;
- use of custom text, media, vector, background, decoration, and primitives;
- how real design-system components combine with custom compositions;
- iterative changes based on actual renders.

Knowledge provides component meaning and usage, not a fixed page template. Layout recipes may be
presented as examples, never mandatory coordinate generators.

### 8.2. MCP design loop

```text
Design plan
→ create target document/page/frames
→ copy or instantiate chosen real components
→ bind content and variants
→ create custom primitives/compositions as needed
→ set layout and coordinates through MCP
→ render affected frame
→ inspect geometry and appearance
→ make targeted creative corrections
→ save checkpoint
```

Operations are grouped by meaningful section and executed with explicit document/page IDs. Each
section has an idempotency namespace so retries do not duplicate frames or instances.

### 8.3. Validation without suppressing creativity

Deterministic validation checks objective failures:

- unintended overlap or clipping;
- overflow and unreachable content;
- broken component/variant/slot references;
- missing font/image/style dependencies;
- unreadable contrast or text size;
- unusable touch targets;
- invalid responsive frame bounds.

It does not rewrite the whole layout into a template or normalize every coordinate. Findings are
fed back to the agent with affected node IDs and screenshots. The agent chooses the correction,
preserving intentional overlaps, asymmetry, and visual experimentation when valid.

## 9. Output-file strategy

For each run/revision:

1. Keep the source `.fig` read-only.
2. Ask OpenPencil MCP to create/open a separate target document.
3. Bring only selected component masters and required dependencies into the target when needed for
   portable real instances.
4. Create screen pages/frames in the target.
5. Save checkpoints after meaningful sections.
6. Save the final output under `designer-data/generated/{session_id}/{run_id}`.
7. Render/focus the final frames in the same OpenPencil workspace for Review 2.

Cross-document component references must be handled explicitly. If OpenPencil cannot preserve a
live external reference, copy the selected master and its dependency closure into an internal
component page of the output. Never copy the entire source design system by default.

## 10. Workflow and Google ADK

Google ADK 2.x is kept simple: LLM agents reason and produce typed decisions; FastAPI and SQLite
own durable state, reviews, retries, and event ordering.

### 10.1. Conversation path

One conversational agent call returns:

```text
chat     → answer normally; no workflow/timeline/MCP
clarify  → ask one useful question
design   → create a durable design run
```

This is LLM-driven, not greeting keyword rules. It avoids duplicate classifier calls and needless
token usage for simple messages.

### 10.2. Durable design states

```text
SPECIFYING
→ SPEC_REVIEW_REQUIRED
→ RETRIEVING_KNOWLEDGE
→ INSPECTING_COMPONENTS
→ RESOLVING_BINDINGS
→ DESIGNING_IN_OPENPENCIL
→ CHECKING_LAYOUT
→ FINAL_REVIEW_REQUIRED
→ COMPLETED
```

Possible recoverable states:

```text
ACTION_REQUIRED
RETRYABLE_FAILURE
CANCELLED
```

Review does not hold an async generator/task in memory. The API invocation ends at a review gate;
the review endpoint persists the decision and starts the next short invocation.

### 10.3. Full design flow

1. Understand the request and recent conversation.
2. Produce typed semantic/responsive UI specification.
3. Show semantic preview and wait for structure approval.
4. Retrieve only relevant knowledge entries.
5. Inspect shortlisted real components through MCP.
6. Resolve exact component, variant, and slot bindings.
7. Create/open the independent output document.
8. Design section by section through MCP with creative freedom.
9. Render/measure and correct the real layout.
10. Save the artifact and request final approval.
11. Apply feedback as a scoped revision without rebuilding unaffected work.

## 11. Backend

Stack:

```text
Python 3.11/3.12
FastAPI + Uvicorn
Pydantic v2
Google ADK >=2,<3
LiteLLM Python library
SQLAlchemy 2 + aiosqlite
MCP Python SDK / HTTP client
structlog
pytest
```

Shallow structure:

```text
backend/
  app/
    main.py
    config.py
    models.py
    routes.py
    chat.py
    workflow.py
    agents.py
    llm.py
    knowledge.py
    components.py
    bindings.py
    openpencil.py
    design.py
    validation.py
    store.py
    stream.py
    errors.py
  prompts/
  tests/
  requirements.txt
  pyproject.toml
```

Rules:

- Root `.env` resolves independently of current working directory.
- LiteLLM uses `LLM_MODEL`, `API_KEY`, and `BASE_URL`.
- Structured outputs accept plain/fenced JSON and validate with Pydantic.
- MCP capability discovery happens at connection time; code does not assume undocumented tools.
- Source/target document handles are explicit and scoped to a run.
- Tool results are normalized before entering LLM context; raw large payloads stay in backend cache.
- No global mutable run state, suspended human-review tasks, or duplicate workflow engines.

## 12. API v1

```text
POST   /api/v1/sessions
GET    /api/v1/sessions
GET    /api/v1/sessions/{session_id}
PATCH  /api/v1/sessions/{session_id}
DELETE /api/v1/sessions/{session_id}

POST   /api/v1/sessions/{session_id}/messages
GET    /api/v1/sessions/{session_id}/messages
GET    /api/v1/sessions/{session_id}/events

GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/reviews
POST   /api/v1/runs/{run_id}/retry
POST   /api/v1/runs/{run_id}/cancel

GET    /api/v1/design-systems
GET    /api/v1/design-systems/{id}/knowledge
POST   /api/v1/design-systems/{id}/inspect

GET    /api/v1/artifacts/{artifact_id}
GET    /api/v1/artifacts/{artifact_id}/preview
GET    /api/v1/artifacts/{artifact_id}/download

GET    /api/v1/settings
PUT    /api/v1/settings
POST   /api/v1/openpencil/test
GET    /api/v1/openpencil/capabilities
```

The frontend sends messages through one endpoint. The backend decides whether the message is chat,
clarification, or a design run.

## 13. Persistence and realtime state

SQLite tables:

```text
sessions
messages
runs
run_revisions
reviews
workflow_events
artifacts
design_systems
knowledge_snapshots
component_evidence
workspace_settings
```

- Every transition has an increasing event sequence.
- SSE supports replay through `Last-Event-ID` and idempotent reducers.
- Session reload restores the actual latest run state and review gate.
- Normal chat messages do not fabricate timeline progress.
- Settings are persisted server-side; local storage is limited to harmless appearance preferences.

## 14. Frontend

Stack:

```text
React + Vite + TypeScript
TanStack Query
small local UI store only where necessary
accessible primitives
Vitest + Testing Library + Playwright
```

Experience:

- Left: collapsible session list and new session.
- Top: horizontal workflow timeline only for a real design run.
- Center: natural chat and concise human-review actions.
- Bottom: composer with screen name, viewport, and selected design system.
- Right: Review / Preview / JSON workbench.
- Settings: OpenPencil MCP connection, design-system source mapping, output directory, appearance.

Timeline requirements:

- Fits the available width and remains readable at all breakpoints.
- Persists throughout the session from backend truth.
- Does not react to ordinary chat.
- Shows knowledge, component inspection, design, layout check, and final review accurately.

Preview requirements:

- Review 1 uses semantic preview.
- During/final design uses actual OpenPencil render output.
- Fit, zoom, fullscreen, independent scrolling, desktop/tablet/mobile frames.
- Long pages retain real scroll height instead of shrinking into a thumbnail.
- No internal property names or debug payloads are rendered as content.

Visual direction:

- Modern, restrained, responsive technical workbench.
- Minimal borders and nested cards.
- No filler AI copy, decorative clutter, or raw technical error cards.
- Accessible focus, keyboard use, contrast, and reduced motion.

## 15. Prompt architecture and token budget

Each English system prompt follows:

```text
ROLE
USER REQUEST
CONTEXT
OUTPUT FORMAT
NEGATIVE PROMPT
```

Agents:

- `conversation`: chat naturally and decide `chat | clarify | design` in one response.
- `specification`: create a flexible UI structure from request and relevant foundations.
- `resolver`: choose from shortlisted real candidates using semantic knowledge and MCP evidence.
- `designer`: plan and execute creative OpenPencil design operations section by section.
- `reviewer`: evaluate real renders and measured findings without redesigning blindly.
- `revision`: apply feedback while preserving unaffected nodes and bindings.

Token controls:

- Never send raw `.fig`, full component list, full MCP response, or full session history.
- Summarize old conversation into durable design decisions.
- Retrieve knowledge by relevant headings/families.
- Cache component evidence and renders by fingerprint.
- Batch compatible requirements into one resolver call.
- Send only affected sections during revisions.
- Do not ask the LLM to repeat tool results already stored as typed state.
- Record estimated input/output tokens per stage.

Token efficiency must reduce irrelevant context, not reduce creative authority over the design.

## 16. Configuration

Root `.env` contains deployment/runtime values. Workspace selections remain configurable from the
frontend and are persisted by the backend.

```dotenv
LLM_MODEL=gemini/gemini-2.5-flash
API_KEY=
BASE_URL=https://litellm.imespro.ai/

DESIGN_DATA_DIR=E:/working/BA/designer-data
BACKEND_PORT=8282
FRONTEND_PORT=3232
OPENPENCIL_PORT=1420
OPENPENCIL_MCP_PORT=7600
```

The effective MCP endpoint is a workspace setting initialized from the configured port. No source
path, document ID, output target, or connection URL is hardcoded in backend/frontend business code.

## 17. Error model

```text
LLM_UNAVAILABLE
LLM_OUTPUT_INVALID
KNOWLEDGE_NOT_FOUND
KNOWLEDGE_STALE
COMPONENT_NOT_FOUND
COMPONENT_INSPECTION_FAILED
SLOT_MAPPING_INVALID
OPENPENCIL_MCP_UNAVAILABLE
OPENPENCIL_CONTEXT_CHANGED
OPENPENCIL_TOOL_FAILED
DESIGN_CHECKPOINT_FAILED
LAYOUT_REVIEW_FAILED
ARTIFACT_SAVE_FAILED
REVIEW_CONFLICT
```

Rules:

- Primary UI never displays TaskGroup messages, tracebacks, Pydantic URLs, or raw RPC JSON.
- Technical detail remains in structured diagnostics/logs.
- Retry is scoped to the failed idempotent stage or section.
- Reconnect refreshes MCP capabilities and runtime document handles.
- If OpenPencil is unavailable during design, preserve the last saved checkpoint and resume later.
- Never report component/build success without verifiable MCP evidence.

## 18. Rebuild phases

### Phase 0 — Freeze and verify the foundation

- Snapshot/archive the current legacy source before deletion.
- Lock the corrected knowledge-first/OpenPencil-native contracts.
- Verify all four `.fig` sources can be opened through the configured MCP root.
- Capture golden requirements for desktop, responsive landing, mobile, and multi-screen cases.

Exit: source registry and MCP capability matrix are known and repeatable.

### Phase 1 — Knowledge and source registry

- Reconcile TapTap and shadcn knowledge with the current `.fig` files.
- Create and review Material UI and Design System v0.3 knowledge.
- Implement semantic family/role/alias/slot routing.
- Add fingerprint, knowledge hash, and drift reporting.

Exit: each golden requirement retrieves relevant families without loading a full catalog.

### Phase 2 — MCP component inspection vertical slice

- Open a source file by stable path.
- Resolve knowledge hints to a small real shortlist.
- Inspect/render exact variants, slots, and dependencies.
- Cache normalized evidence without exposing raw file trees to the LLM.

Exit: one known component from every design system is selected and verified through MCP.

### Phase 3 — Slot mapping and real component use

- Implement text/image/icon/variant/visibility/instance/content-zone mappings.
- Copy/use selected components in a separate output document.
- Bind real content and verify component integrity.

Exit: a portable output file contains a real component with verified overridden content.

### Phase 4 — Simple backend and chat

- Rebuild versioned FastAPI API, SQLite, SSE replay, typed errors, LiteLLM, and ADK agents.
- Make ordinary chat reliable and inexpensive first.
- Add durable specification review without suspended tasks.

Exit: chat works naturally; a design request reaches Review 1 and survives restart.

### Phase 5 — Creative OpenPencil design loop

- Implement target document/page creation and checkpointing.
- Allow the designer agent to create flexible frames, primitives, components, coordinates, and
  responsive compositions through MCP.
- Render after meaningful sections and apply targeted visual iterations.
- Ensure retries do not duplicate work.

Exit: golden desktop and mobile outputs are designed and saved entirely through OpenPencil MCP.

### Phase 6 — Layout review and revisions

- Add objective geometry/accessibility checks.
- Feed real screenshots and affected-node findings to the reviewer/designer.
- Preserve intentional creative choices and revise only failed/feedback sections.
- Add durable final review and handoff.

Exit: both review gates and scoped revision work end to end.

### Phase 7 — Clean frontend

- Rebuild chat, timeline, composer, settings, review, preview, zoom, fullscreen, and responsive shell.
- Persist settings and selected source correctly.
- Hide raw workflow/debug events from normal users.

Exit: UI state matches backend/MCP truth across reload and reconnect.

### Phase 8 — Hardening and cutover

- Run E2E, failure injection, MCP reconnect, Windows/Docker mount, performance, and accessibility
  tests.
- Delete Penpot code, display-only/headless-compiler experiments, duplicate state machines,
  ephemeral source-tab logic, stale prompts, unused CSS, and debug messages.
- Keep only the new path after golden tests pass.

Exit: V3 is the sole runtime implementation.

## 19. Testing

Backend/contracts:

- Knowledge retrieval returns relevant families only.
- Captured prompts never contain raw `.fig`, full trees, or full catalogs.
- Source fingerprint and knowledge drift behavior.
- Component shortlist, MCP verification, and evidence cache.
- Slot mapping and stale/ambiguous remapping.
- Durable reviews, state transitions, SSE replay, and scoped retries.

OpenPencil integration:

- Open each of the four source files by path without relying on a previously open tab.
- Inspect/render selected real components.
- Create a separate output and use real components with overrides.
- Build desktop/tablet/mobile frames with creative layouts.
- Save/reopen artifacts without broken references or missing dependencies.
- Disconnect/reconnect MCP and resume from checkpoints.

Frontend/E2E:

- Pure chat does not show or advance the timeline.
- Settings survive reload and never revert silently.
- Review 1, component inspection, design, check, and Review 2 map to real states.
- Preview supports fit, zoom, fullscreen, responsive frames, and long-page scrolling.
- User feedback revises only affected design sections.

## 20. Acceptance criteria

Functional:

- Knowledge supplies semantic indexing and component usage guidance for all four design systems.
- The LLM receives only relevant knowledge and small verified candidate evidence.
- Agent can inspect the real component appearance/sample before choosing it.
- Agent uses real components and verified slot mappings when appropriate.
- Agent retains freedom over composition, coordinates, responsive behavior, primitives, and visual
  creativity.
- OpenPencil MCP is used to design, render, save, and show the final output.
- Output is separate from immutable source files and remains editable in OpenPencil.

Reliability:

- No dependence on `tab-1`, manually focused files, or stale saved document IDs.
- Source selection uses stable design-system IDs and paths from persisted settings.
- Large source files do not enter prompt context.
- MCP reconnect and section retry do not duplicate nodes.
- A failed step never produces synthetic success.

Quality:

- Backend: Python, FastAPI, SQLite, Google ADK 2.x, LiteLLM.
- Frontend: React, Vite, TypeScript, responsive and accessible.
- Root structure remains `backend/`, `frontend/`, `infra/`, plus docs/config files.
- Files stay below 300 lines and folders remain shallow.
- No hardcoded connection/source/output settings or obsolete runtime path.

## 21. First implementation milestone

The first proof of the corrected philosophy is:

```text
User requests a simple commerce hero
→ agent reads only relevant TapTap knowledge
→ knowledge identifies Button and supporting families
→ MCP opens the TapTap source and renders a few real candidates
→ agent selects a component after seeing actual evidence
→ slot mapping binds Vietnamese content
→ agent freely designs desktop and mobile hero frames through MCP
→ MCP renders, agent improves the actual layout, saves, and shows the result
```

This must pass before rebuilding the entire frontend. It proves semantic knowledge, selective
component inspection, controlled data mapping, creative MCP design, and real OpenPencil output in
one vertical slice.
