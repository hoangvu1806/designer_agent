# Agentic Designer V2 — Greenfield Rebuild Plan

> **Superseded on 2026-09-03.** The authoritative rebuild direction is
> [`REBUILD_V3_PLAN.md`](./REBUILD_V3_PLAN.md). V2 relied on OpenPencil/Penpot MCP for component
> discovery and assembly; V3 reads source `.fig` files headlessly, compiles independent
> artifacts, and uses OpenPencil MCP only to display the result.

> Integration update (2026-09-01): OpenPencil replaces Penpot. The approved workflow
> and product boundaries remain unchanged; `OPENPENCIL_DECISION.md` is authoritative
> for design-file integration, MCP ownership, file output, and component reuse.

> Trạng thái: brainstorm và kế hoạch kiến trúc, **chưa triển khai code**.  
> Phạm vi: viết lại source mới; không port tuần tự runtime Node.js hiện tại.  
> Nguyên tắc: đơn giản, typed, cây thư mục nông, mỗi file source tối đa 300 dòng.

## 1. Câu chuyện sản phẩm

V2 giữ đúng một luồng dễ hiểu:

```text
Yêu cầu tự nhiên
→ UI specification có cấu trúc
→ Người dùng duyệt
→ Tìm component thật
→ Gắn dữ liệu vào component
→ Dựng trên Penpot
→ Kiểm tra layout
→ Người dùng duyệt lần cuối
```

Sản phẩm phải kết hợp được hai năng lực:

1. Linh hoạt tạo hierarchy, layout, responsive behavior và nội dung theo yêu cầu.
2. Dùng đúng Library Component, variant và text slot thật trong Penpot khi dựng bản cuối.

Kết quả cuối phải nằm trong **target file/page riêng**, được Penpot lưu và có link mở/share. File Design System chỉ cung cấp component, không còn là nơi chứa thiết kế sinh ra.

## 2. Checklist yêu cầu bắt buộc

| Yêu cầu | Quyết định V2 |
|---|---|
| Backend Python | Python 3.12+, FastAPI, Pydantic v2, pydantic-settings |
| Google ADK > 2.0 | Dùng ADK 2.x `Workflow` graph; lock exact version sau compatibility spike |
| LLM qua LiteLLM | Một provider adapter duy nhất, cấu hình từ `.env` |
| API chuẩn, có version | Tất cả endpoint nghiệp vụ dưới `/api/v1` |
| Frontend | React + Vite + TypeScript |
| Ba folder chính | `backend/`, `frontend/`, `infra/`; root có `docs/`, README, `.env.example` |
| MCP do FE quản lý | FE quản lý profile, connect/test, target và library; backend làm execution proxy theo profile của phiên |
| Đổi library nhanh | Chọn một/nhiều library tại composer và Settings; snapshot theo run |
| Output tách library | Dựng vào target file/page đang mở plugin và dùng Design System như connected library |
| Lưu/share | Trả `file_id`, `page_id`, `board_id`, `share_url` |
| UI chatbot | Chat ở trung tâm, session rail bên trái, review/preview bên phải |
| Timeline | Một đường ngang ở phía trên workspace |
| Session rail | Tạo mới, tìm, mở lại, expand/collapse |
| Composer | Screen name, target, libraries, prompt |
| Settings | MCP, Penpot, libraries, connection test, capability |
| Realtime | SSE có sequence, reconnect và replay |
| Visual style | Hiện đại, ít border, không card lồng card, không text thừa |
| Folder nông | Không sâu quá 2 cấp logic dưới mỗi folder chính |
| File ngắn | Mỗi file source không quá 300 dòng; target 200–260 |
| Prompt | ROLE → USER REQUEST → CONTEXT → OUTPUT FORMAT → NEGATIVE PROMPT |
| Không tự cài | Chỉ định nghĩa requirements; dùng venv `base` hiện có khi triển khai |

## 3. Penpot: tách nguồn component và đích thiết kế

### 3.1. Vấn đề của V1

V1 đang gộp ba khái niệm:

- File đang mở MCP plugin.
- File chứa Design System.
- File nhận thiết kế mới.

Điều này khiến layout bị ghi vào file component, khó tìm trên Dashboard, dễ chồng tọa độ và tạo cảm giác “không có sản phẩm mới”.

### 3.2. Mô hình V2

Mỗi session lưu hai context độc lập:

```text
Component source
  connection_profile_id
  library_ids[]
  library_snapshot_version

Design target
  target_mode
  file_id
  page_id
  plugin_instance_id
```

Luồng Penpot khuyến nghị:

1. Người dùng tạo/mở một target file trắng.
2. Target file kết nối Design System dưới dạng shared/connected library.
3. Người dùng mở MCP plugin trong target file.
4. FE test connection và đọc current file/page/connected libraries.
5. Mỗi run tạo một page hoặc board namespace riêng trong target file.
6. Component instance được tạo từ connected library nên vẫn là component thật.
7. Penpot tự lưu; V2 trả link mở/share artifact.

Target modes:

```text
new_page       # mặc định; mỗi run/revision một page riêng
existing_page  # append/replace board có namespace
new_file       # optional; chỉ bật khi management adapter hỗ trợ
```

`new_file` không được coi là capability mặc định của MCP plugin. Nếu self-host có API quản lý phù hợp, bổ sung `PenpotManagementAdapter` sau. Nếu không có, FE hướng dẫn tạo/mở file trắng rồi tiếp tục. Không gọi undocumented internal API mặc định.

### 3.3. FE quản lý MCP theo mô hình hybrid

Ba phương án đã cân nhắc:

1. Browser trực tiếp làm toàn bộ MCP: nhanh nhưng vướng CORS/PNA, reload và credential.
2. Backend sở hữu toàn bộ MCP: ổn định nhưng FE thiếu linh hoạt.
3. **Hybrid control plane — chọn phương án này.**

```text
Frontend control plane
  ├── tạo/sửa connection profile
  ├── connect/disconnect/test
  ├── chọn target file/page
  ├── chọn component libraries
  └── snapshot cấu hình vào session/run

Backend execution plane
  ├── nhận profile đã chọn
  ├── gọi MCP theo lifecycle ngắn hoặc pooled
  ├── discover/assemble/serialize có timeout + idempotency
  └── trả capability/artifact về FE
```

Như vậy FE thực sự quản lý kết nối và lựa chọn, còn backend giữ execution để graph resume, retry và audit được.

### 3.4. Quy tắc ghi Penpot

- Không ghi vào source library file, trừ khi user chủ động chọn và xác nhận cảnh báo.
- Plugin data bắt buộc: `run_id`, `revision`, `screen_id`, `node_id`, `component_id`.
- Page/board name: `{screen_name} · r{revision}`.
- Retry tìm artifact theo namespace trước khi tạo mới.
- Assembly theo section/batch, có checkpoint từng batch.
- Serialize chỉ artifact của run hiện tại, không đọc toàn file/library.
- Layout engine điều khiển container/flex/grid; component chỉ cung cấp appearance/behavior nội tại.
- Không chọn component sai chỉ vì tên gần giống; không phù hợp thì `unresolved` rõ ràng.
- Trước mỗi batch phải xác minh active file/page chưa đổi; nếu đổi thì dừng `PENPOT_CONTEXT_CHANGED`.

## 4. Kiến trúc tổng thể

```text
┌──────────────────────────── React + Vite ────────────────────────────┐
│ Session rail │ Timeline │ Chat + composer │ Review/Preview/JSON     │
│ MCP profiles │ Target file/page │ Multi-library picker │ SSE state │
└──────────────────────────── REST + SSE ──────────────────────────────┘
                                  │
┌──────────────────────────────── FastAPI ─────────────────────────────┐
│ API v1 │ Run service │ ADK Workflow │ Contracts │ Event store       │
│ LiteLLM provider │ Resolver │ Penpot execution proxy │ Persistence  │
└────────────────────── HTTP / Streamable MCP ─────────────────────────┘
                                  │
┌──────────────────────────────── Penpot ──────────────────────────────┐
│ Target file/page + plugin │ Connected libraries │ Saved artifact    │
└──────────────────────────────────────────────────────────────────────┘
```

Không dùng microservices ở baseline. Một FastAPI process và một React app là đủ. Chỉ thêm worker/queue nếu profiling chứng minh cần.

## 5. Google ADK 2.x workflow graph

ADK 2.0 `Workflow` graph là source of truth cho execution và transition. Không viết thêm một state machine độc lập ở frontend.

```text
START
  → normalize_request
  → analyze_requirement [LLM]
  → validate_ui_spec
  → WAIT_REVIEW_SPEC

APPROVE_SPEC
  → snapshot_penpot_context
  → discover_components [MCP]
  → resolve_bindings [LLM + deterministic validation]
  → bind_content
  → validate_resolved_spec
  → assemble_sections [MCP batches]
  → serialize_target
  → inspect_layout [deterministic + LLM]
  → WAIT_REVIEW_FINAL

APPROVE_FINAL  → persist_handoff → FINISHED
REQUEST_CHANGE → revise_ui_spec → validate_ui_spec → WAIT_REVIEW_SPEC
RETRYABLE      → retry_failed_node
BLOCKED        → user_action_required
```

### 5.1. LLM nodes

- `analyze_requirement`: natural language → typed UI specification.
- `resolve_bindings`: requirement → real component/variant/text slots.
- `revise_ui_spec`: áp dụng feedback nhưng giữ các quyết định đã duyệt.
- `inspect_layout`: đánh giá telemetry đo được, không tự đoán geometry.

### 5.2. Deterministic nodes

- Normalize request/context.
- Schema + semantic validation.
- Generate component queries.
- MCP capability check và library snapshot.
- Candidate discovery/ranking pre-filter.
- Validate component ID, variant, text slot.
- Bind content.
- Compile Penpot operations.
- Execute idempotent batches.
- Serialize đúng target artifact.
- Compute bounds, overflow, overlap, flex/grid invariants.
- Persist event/review/artifact.

### 5.3. Human-in-the-loop bền vững

- Review không giữ coroutine/promise trong RAM.
- Graph kết thúc invocation tại `WAIT_REVIEW_*`.
- Review endpoint persist decision rồi resume từ ADK session/event state.
- Node idempotency key: `{run_id}:{revision}:{node}:{attempt}`.
- FE reload bằng run snapshot + SSE từ sequence gần nhất.

## 6. Domain contracts

Pydantic là source of truth; TypeScript types sinh từ OpenAPI.

Model cốt lõi:

```text
Session
McpConnectionProfile
PenpotContext
LibrarySnapshot
GenerationRun
RunRevision
UiSpecification
UiNode
ComponentRequirement
ComponentCandidate
ComponentBinding
ResolvedUiSpecification
AssemblyArtifact
LayoutTelemetry
LayoutReview
ReviewDecision
WorkflowEvent
```

`UiNode` cần linh hoạt nhưng không mơ hồ:

- `kind`: container | component | text | media.
- `layout`: block | flex | grid | absolute.
- `responsive`: base + breakpoint overrides.
- `sizing`: fixed | fill | hug | min/max.
- `content`: semantic props, không chứa Penpot code.
- `component_requirement`: role, variant intent, required slots/capabilities.
- `binding`: chỉ xuất hiện sau resolver.

LLM không được sinh JavaScript Penpot. Backend compile typed spec thành operations.

## 7. Backend

### 7.1. Stack

```text
Python 3.12+
FastAPI + Uvicorn
google-adk >=2.0,<3.0 (lock exact version)
LiteLLM
Pydantic v2 + pydantic-settings
SQLAlchemy 2 + aiosqlite mặc định
httpx
MCP Python SDK
structlog
pytest + pytest-asyncio
ruff + mypy
```

Không tự chạy `pip install`; chỉ tạo requirements để dùng với venv `base` hiện có khi bắt đầu code.

### 7.2. Cấu trúc backend nông

```text
backend/
  app/
    main.py          # app factory, lifespan, middleware
    config.py        # Settings từ root .env
    api.py           # include versioned routers
    routes.py        # session/run/review endpoints
    integrations.py  # MCP/Penpot endpoints
    models.py        # domain + API Pydantic models
    workflow.py      # ADK graph declaration
    nodes.py         # deterministic nodes
    agents.py        # LLM agent definitions
    prompts.py       # prompt loader/rendering
    llm.py           # LiteLLM adapter
    penpot.py        # gateway + compiler
    store.py         # repositories/persistence
    stream.py        # SSE publisher/replay
    errors.py        # typed errors
  prompts/
    analyzer.md
    resolver.md
    layout-review.md
    revision.md
  tests/
    test_api.py
    test_workflow.py
    test_contracts.py
    test_penpot.py
    fixtures.py
  requirements.txt
  requirements-dev.txt
  pyproject.toml
```

Không tạo chuỗi `app/services/integrations/penpot/...`. Khi một file gần 300 dòng, tách ngang cùng cấp, ví dụ `penpot.py` thành `penpot_client.py` và `penpot_compile.py`.

### 7.3. LiteLLM adapter

```python
class LlmProvider(Protocol):
    async def structured(
        self, *, prompt: str, schema: type[BaseModel]
    ) -> BaseModel: ...
```

- Model, base URL, API key, timeout, retry lấy từ Settings.
- LLM nodes dùng structured output theo Pydantic schema.
- Retry chỉ cho network/rate limit/invalid output, có giới hạn.
- Log model/token/latency; không log secret.

## 8. API v1

### 8.1. Session và run

```text
POST   /api/v1/sessions
GET    /api/v1/sessions
GET    /api/v1/sessions/{session_id}
PATCH  /api/v1/sessions/{session_id}
DELETE /api/v1/sessions/{session_id}

POST   /api/v1/sessions/{session_id}/runs
GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/reviews
POST   /api/v1/runs/{run_id}/retry
POST   /api/v1/runs/{run_id}/cancel
GET    /api/v1/runs/{run_id}/events
```

### 8.2. MCP/Penpot control plane

```text
POST   /api/v1/mcp/connections/test
GET    /api/v1/mcp/capabilities
GET    /api/v1/penpot/context
GET    /api/v1/penpot/libraries
POST   /api/v1/penpot/libraries/inspect
POST   /api/v1/penpot/targets/prepare
GET    /api/v1/penpot/artifacts/{artifact_id}
```

Không đưa token, prompt hoặc JSON lớn vào query string. Error trả `application/problem+json` gồm `code`, `title`, `detail`, `retryable`, `action`.

### 8.3. SSE contract

```json
{
  "id": "evt_uuid",
  "runId": "run_uuid",
  "revision": 1,
  "sequence": 18,
  "type": "assembly.section.completed",
  "time": "ISO-8601",
  "payload": {}
}
```

Event tối thiểu:

```text
run.created
run.state.changed
spec.started
spec.completed
review.required
review.recorded
discovery.started
discovery.completed
binding.completed
assembly.started
assembly.section.completed
assembly.completed
layout.started
layout.completed
run.blocked
run.failed
run.completed
```

FE reconnect bằng `Last-Event-ID` hoặc `after_sequence`; reducer phải idempotent.

## 9. Frontend

### 9.1. Stack

```text
React + Vite + TypeScript
React Router
TanStack Query
Zustand chỉ cho local UI/connection state nhỏ
Zod tại runtime boundary nếu cần
Tailwind CSS
Radix primitives
Một bộ icon duy nhất: Lucide hoặc Phosphor
Vitest + Testing Library + Playwright
```

### 9.2. Cấu trúc frontend nông

```text
frontend/
  src/
    main.tsx
    app.tsx
    router.tsx
    api.ts
    types.ts
    events.ts
    store.ts
    styles.css
    components/
      AppShell.tsx
      SessionRail.tsx
      WorkflowTimeline.tsx
      ChatThread.tsx
      Composer.tsx
      ReviewPanel.tsx
      PreviewCanvas.tsx
      SettingsPanel.tsx
      ConnectionPicker.tsx
    features/
      sessions.ts
      generation.ts
      review.ts
      penpot.ts
  tests/
    app.test.tsx
    events.test.ts
    e2e.spec.ts
  package.json
  vite.config.ts
  tsconfig.json
```

Không tạo component chỉ để bọc một `div`. Chỉ tách khi có state, behavior, accessibility contract hoặc reuse.

## 10. UX/UI direction

### 10.1. Định vị

Đây là **design operations workbench** cho designer/BA làm việc với agent và Penpot, không phải chatbot phổ thông hay dashboard analytics.

Single job: biến yêu cầu thành thiết kế Penpot có component thật, với hai điểm duyệt rõ ràng.

### 10.2. Desktop wireframe

```text
┌───────┬────────────────────────────────────────────────────────────┐
│       │ Requirement ─ Spec ─ Components ─ Build ─ Check ─ Final  │
│ Sess. ├────────────────────────────────┬───────────────────────────┤
│ rail  │                                │ Review / Preview / JSON   │
│       │ Chat thread                    │ Contextual panel          │
│       │                                │                           │
│       ├────────────────────────────────┴───────────────────────────┤
│       │ [Screen] [Target] [Libraries +] Describe…        [Create] │
└───────┴────────────────────────────────────────────────────────────┘
```

- Session rail: 264px expanded, 68px collapsed.
- Timeline ngang phía trên, không lặp thành workflow sidebar.
- Chat là vùng chính; system events gom theo stage, không biến mọi event thành bubble.
- Right panel 400–480px, tabs thay đổi theo stage.
- Composer sticky dưới cùng.

Tablet:

- Session rail collapsed mặc định.
- Right panel thành drawer hoặc split khoảng 45%.

Mobile:

- Header + timeline cuộn ngang có snap.
- Tabs `Chat`, `Preview`, `Review`.
- Composer sticky; library picker mở bottom sheet.

### 10.3. Visual language

Định hướng: **quiet technical canvas** — một bàn làm việc thiết kế chính xác, không phải SaaS template.

```text
Canvas Ink       #17181C  text chính
Paper            #F7F8FA  nền ứng dụng
Workbench        #FFFFFF  surface
Signal Violet    #6657E8  active/action
Approval Mint    #1E9D72  connected/success
Review Amber     #C77A18  waiting/review
Fault Coral      #D84A4A  error/blocked
```

Typography:

- UI/body: Manrope hoặc system fallback.
- ID/JSON/telemetry: IBM Plex Mono.

Signature element:

- Timeline là một “live build rail”: đường liên tục đổi trạng thái theo stream; focus/hover mở stage detail. Đây là sequence thật nên marker có ý nghĩa.

Restraint:

- Không card trong card.
- Không gradient trang trí, glassmorphism hoặc shadow dày.
- Border chỉ dùng cho input/focus/separator/error.
- Hierarchy bằng spacing, surface tone và type weight.
- Motion 160–220ms, tôn trọng reduced motion.
- Không emoji làm structural icon.

Copy:

- Dùng `Create design`, `Approve structure`, `Request changes`, `Open in Penpot`.
- Không dùng “Mình đã hiểu…”, “AI đang suy nghĩ…”, “magic”.
- Error phải nói nguyên nhân và hành động tiếp theo.

### 10.4. Composer

```text
Screen name
Target file/page
Libraries multi-select + Add library
Natural-language request
Create / Send revision
```

Library selection lưu theo session nhưng snapshot theo run để đổi library không làm thay đổi run đang chạy.

### 10.5. Settings

```text
Connections  # MCP URL, test, connect/disconnect, capability
Penpot       # current file/page, target strategy, share URL
Libraries    # connected libraries, count, refresh/cache
Models       # effective LiteLLM model; không hiển thị secret
Appearance   # theme, density, reduced motion
```

## 11. Preview và review

Preview semantic chạy từ `UiSpecification` trước Penpot để Review 1 có giá trị. Sau assembly, right panel chuyển sang Penpot artifact/telemetry.

Preview engine:

- Mobile/tablet/desktop viewport.
- Fit/50/75/100%.
- Long page scroll đúng, không co thành thumbnail.
- Flex/grid/responsive container.
- Multi-screen tabs.
- Structure ↔ Preview highlight.
- Placeholder có unresolved reason.

Review 1:

- Structure tree.
- Semantic preview.
- Screen/viewport/responsive rules.
- Approve hoặc feedback.

Review 2:

- Target file/page và `Open in Penpot`.
- Binding summary.
- Overflow/overlap/flex/grid findings.
- Unresolved/fallback items.
- Approve hoặc feedback.

## 12. System prompts

Mỗi node có prompt tiếng Anh riêng, ngắn nhưng đủ ràng buộc. Không dùng một prompt khổng lồ.

Template bắt buộc:

```text
ROLE
You are ...

USER REQUEST
{{user_request}}

CONTEXT
{{typed_context}}

OUTPUT FORMAT
Return only JSON matching {{schema_name}}. ...

NEGATIVE PROMPT
Do not ...
```

### 12.1. Analyzer

```text
ROLE
You are a product UI architect. Convert intent into a responsive, semantic UI specification while remaining visually flexible.

USER REQUEST
{{user_request}}

CONTEXT
Screen name, target platform, viewport, prior feedback, and allowed UI contract.

OUTPUT FORMAT
Return only valid UiSpecification JSON. Define hierarchy, content, layout, sizing, responsive behavior, component requirements, and stable node IDs.

NEGATIVE PROMPT
Do not emit Penpot code, component IDs, unnecessary absolute coordinates, commentary, or unsupported fields.
```

### 12.2. Resolver

```text
ROLE
You are a design-system component resolver. Select the best real component for each requirement without inventing metadata.

USER REQUEST
{{user_request}}

CONTEXT
UI requirements and inspected Penpot candidates with IDs, variants, capabilities, bounds, and text slots.

OUTPUT FORMAT
Return only ComponentBindingSet JSON. Bind exact IDs, variants, slots, confidence, and explicit unresolved reasons.

NEGATIVE PROMPT
Do not fabricate components or slots, choose by name alone, alter layout intent, or hide unresolved requirements.
```

### 12.3. Layout reviewer

```text
ROLE
You are a UI layout reviewer. Judge usability and spatial integrity from measured telemetry.

USER REQUEST
{{user_request}}

CONTEXT
Resolved specification, viewport rules, bindings, and serialized Penpot bounds/flex/grid telemetry.

OUTPUT FORMAT
Return only LayoutReview JSON with status, findings, affected node IDs, severity, and actionable fixes.

NEGATIVE PROMPT
Do not invent measurements, redesign the product, ignore overflow, or return prose outside JSON.
```

### 12.4. Revision planner

```text
ROLE
You revise an existing UI specification from explicit human feedback while preserving approved decisions.

USER REQUEST
{{feedback}}

CONTEXT
Current specification, review checkpoint, validation findings, and immutable bindings when applicable.

OUTPUT FORMAT
Return only a complete revised UiSpecification JSON and preserve stable IDs for unchanged nodes.

NEGATIVE PROMPT
Do not reset unaffected sections, remove requirements silently, emit code, or add commentary.
```

## 13. Persistence

Local mặc định dùng SQLite qua `DATABASE_URL`; production có thể đổi PostgreSQL mà không đổi repository contract.

```text
sessions
runs
revisions
reviews
events
artifacts
connection_profiles
library_snapshots
```

- Không lưu full recursive metadata của 2.244 components vô hạn.
- Snapshot chỉ lưu candidate đã dùng, fingerprint và TTL.
- FE lưu UI preferences/non-secret profile trong IndexedDB.
- Backend là source of truth cho session/run/review/event.

## 14. Root `.env` và ports

Root `.env` là nguồn cấu hình local duy nhất. Commit `.env.example`, không commit `.env`.

```dotenv
# App
APP_ENV=development
APP_HOST=127.0.0.1
BACKEND_PORT=8000
FRONTEND_PORT=5173
LOG_LEVEL=INFO
DATABASE_URL=sqlite+aiosqlite:///./data/agentic_designer.db
CORS_ORIGINS=http://localhost:5173

# LiteLLM
LITELLM_API_BASE=http://localhost:4000
LITELLM_API_KEY=
LITELLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=90
LLM_MAX_RETRIES=2

# ADK
ADK_APP_NAME=agentic-designer
ADK_SESSION_DB_URL=sqlite:///./data/adk_sessions.db

# Penpot
PENPOT_PUBLIC_URL=http://localhost:9001
PENPOT_PORT=9001
PENPOT_VERSION=2.17.2

# MCP defaults; FE có thể override theo profile
MCP_PLUGIN_PORT=4400
MCP_HTTP_PORT=4401
MCP_WS_PORT=4402
MCP_DEFAULT_URL=http://localhost:4401/mcp
MCP_TIMEOUT_SECONDS=30
MCP_ASSEMBLY_BATCH_SIZE=1

# Optional infra
POSTGRES_PORT=5432
REDIS_PORT=6379
```

Backend resolve root `.env` tuyệt đối, không phụ thuộc current working directory.

## 15. Repository đích

```text
Agent_Designer/
  backend/
    app/
    prompts/
    tests/
    requirements.txt
    requirements-dev.txt
    pyproject.toml

  frontend/
    src/
    tests/
    package.json
    vite.config.ts
    tsconfig.json

  infra/
    compose.yaml
    penpot.env
    nginx.conf
    README.md

  docs/
    REFACTOR_V2_PLAN.md
    ARCHITECTURE.md
    API.md
    PENPOT_MCP.md

  .env.example
  .gitignore
  README.md
```

Chỉ `backend`, `frontend`, `infra` chứa source/runtime; `docs` chỉ chứa tài liệu.

## 16. Infra/Docker

`infra/compose.yaml` có profiles:

```text
penpot  # Penpot frontend/backend/exporter/db/redis/mcp
app     # backend + frontend, optional local
full    # tất cả
```

Image version, port và public URL lấy từ root `.env`; không hardcode trong compose.

Mục tiêu vận hành về sau:

```text
docker compose --env-file ../.env --profile penpot up -d
uvicorn app.main:app --reload --port $BACKEND_PORT
npm run dev -- --port $FRONTEND_PORT
```

Đây chỉ là kế hoạch; không chạy/cài các lệnh trên ở giai đoạn brainstorm.

## 17. Quy tắc code quality

- Mỗi file source tối đa 300 dòng; target 200–260.
- Function target dưới 40 dòng; mỗi graph node một trách nhiệm.
- Không `dict[str, Any]` cho contract chính.
- Không global mutable run state.
- Không waiter chờ review trong RAM.
- Không duplicate state machine ở FE/BE.
- Không `utils.py` tổng hợp; helper ở cùng domain sở hữu.
- Không catch mọi lỗi rồi trả `fetch failed`.
- Không log full prompt/tree ở INFO.
- Public function có type hints.
- OpenAPI sinh TypeScript types.
- CI có line-count guard, ruff, mypy, pytest, ESLint, TypeScript, Vitest.

## 18. Error model

```text
VALIDATION_ERROR
REVIEW_CONFLICT
MCP_UNREACHABLE
MCP_PLUGIN_NOT_CONNECTED
PENPOT_CONTEXT_CHANGED
LIBRARY_NOT_CONNECTED
COMPONENTS_UNRESOLVED
COMPONENT_SLOT_MISMATCH
ASSEMBLY_TIMEOUT
ASSEMBLY_PARTIAL
LAYOUT_INVALID
LLM_OUTPUT_INVALID
```

Mỗi lỗi có human message, technical code, `retryable`, suggested action và correlation run/revision/stage.

## 19. Testing

Backend:

- Contract/schema/semantic validators.
- ADK graph routing/resume.
- Approve/change/stale review.
- LiteLLM structured-output retry.
- MCP capability/context change.
- Library switching và snapshot isolation.
- Resolver không fabricate component/slot.
- Batch assembly idempotency.
- Scoped serialization.
- Mobile/desktop/multi-screen/long-page fixtures.

Frontend:

- SSE reconnect/idempotency.
- Session rail collapse/new/open.
- Timeline mapping.
- Composer target/library/screen selection.
- Review và conflict handling.
- Settings connection test.
- Responsive 375/768/1024/1440.
- Keyboard/focus/contrast/axe.

Live Penpot smoke test tách riêng khỏi unit suite mặc định.

## 20. Lộ trình greenfield

### Phase 0 — Contract và spike

- Freeze golden inputs: mobile, desktop, long landing, multi-screen.
- Spike ADK 2.x graph + LiteLLM structured output.
- Spike target context, connected library và share URL.
- Khóa exact versions.

Exit: graph chạy `START → WAIT_REVIEW_SPEC`; MCP đọc target + connected library.

### Phase 1 — Foundation

- Tạo ba folder mới và `.env.example`.
- FastAPI settings/errors/health.
- Pydantic contracts + OpenAPI.
- SQLite repositories + event sequence.
- React shell + design tokens.

Exit: backend/frontend chạy độc lập; không import V1.

### Phase 2 — Spec + Review 1

- Analyzer prompt/agent.
- UI spec validators.
- Semantic preview.
- Chat/session/timeline/review UI.
- Durable Review 1.

Exit: request → spec → preview → approve/revise, không cần Penpot.

### Phase 3 — FE MCP control plane

- Connection profiles và Settings.
- Test/connect/disconnect/status.
- Current file/page/capabilities.
- Multi-library picker + snapshot.
- Target preparation.

Exit: source libraries và design target hiển thị tách biệt.

### Phase 4 — Component resolution

- Query generator.
- Bounded discovery + cache.
- Resolver prompt.
- Binding/text-slot validation.
- Unresolved review UX.

Exit: mỗi component node có binding thật hoặc reason rõ ràng.

### Phase 5 — Assembly

- Operation compiler.
- New-page/existing-page target.
- Section batching + context guard.
- Idempotency/plugin data.
- Open/share artifact.

Exit: output không nằm trong source library; retry không duplicate.

### Phase 6 — Layout check + Review 2

- Scoped serialization.
- Deterministic telemetry.
- Layout reviewer.
- Final review/handoff.

Exit: full workflow hoàn chỉnh và resume được.

### Phase 7 — Hardening/cutover

- E2E + live MCP matrix.
- Accessibility/performance/security.
- Docs/runbook.
- Archive V1 chỉ sau khi golden cases pass.

## 21. Acceptance criteria

Functional:

- Natural request tạo valid spec cho mobile/desktop.
- Hai review resume sau reload/server restart.
- FE thêm/đổi MCP profile và libraries không restart server.
- Source library và target hiển thị tách biệt.
- Output mặc định vào page/board riêng trong target file.
- Instance giữ component/library/variant/text-slot thật.
- Layout linh hoạt flex/grid/responsive, không phải template xếp dọc.
- Artifact mở/share được từ UI.

Reliability:

- SSE reconnect không duplicate.
- Context đổi không ghi nhầm file.
- Timeout một section retry đúng section.
- Không serialize cả library khi review một board.
- Unresolved component không crash graph.

UX:

- Session rail co/giãn và tạo phiên mới.
- Timeline ngang phản ánh đúng luồng.
- Right panel contextual.
- Composer chọn screen/target/library.
- Settings test connection và hướng dẫn sửa lỗi.
- Không border/card/text thừa hoặc raw technical error.

Code:

- Không file source trên 300 dòng.
- Không folder source sâu quá 2 cấp logic.
- Contracts FE/BE không drift.
- Quality gates pass.
- Secret/runtime artifact không vào Git.

## 22. Không làm trong baseline

- Không tự động cài package hoặc tạo venv.
- Không microservices/Kafka/Celery khi chưa cần.
- Không auth/organization phức tạp trong vertical slice đầu.
- Không tự tạo Penpot file bằng undocumented API mặc định.
- Không cho LLM sinh arbitrary Penpot JavaScript.
- Không tuyên bố preview semantic là pixel-perfect Penpot.
- Không port CSS/DOM/state machine của `interactive_designer`.

## 23. Nguồn tham khảo

Repository:

```text
E:/working/BA/UAIP-business-analysis-agent
branch: one-graph
```

Chỉ tái sử dụng pattern một graph chính, typed I/O, deterministic validation và persisted event/session. Không sao chép cấu trúc subgraph nhiều tầng vì trái yêu cầu folder nông.

ADK 2.0:

- https://github.com/google/adk-python/blob/main/docs/guides/workflow/graph/index.md
- https://github.com/google/adk-python/blob/main/docs/guides/workflow/workflow/index.md
- https://github.com/google/adk-docs/blob/main/docs/2.0/index.md

Penpot:

- https://help.penpot.app/plugins/api/
- https://help.penpot.app/user-guide/account-teams/projects-files/

## 24. Quyết định khuyến nghị để bắt đầu

1. Chọn hybrid MCP control plane.
2. Chọn `new_page` mặc định; `new_file` là optional capability.
3. SQLite local, giữ `DATABASE_URL` để đổi PostgreSQL.
4. Một ADK 2.x `Workflow` graph duy nhất.
5. Hoàn thành vertical slice Review 1 không Penpot trước.
6. Không tiếp tục thêm feature vào V1 ngoài blocker; feature mới đi vào source mới.

Vertical slice đầu tiên:

```text
Create session
→ natural request
→ ADK analyzer through LiteLLM
→ validated UI specification
→ streamed timeline/chat
→ responsive semantic preview
→ durable Review 1
```

Slice này chứng minh graph, contract, UI, streaming và review mới trước khi đưa độ phức tạp của Penpot vào.
