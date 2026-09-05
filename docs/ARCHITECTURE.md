# Architecture

> **Legacy architecture.** It is superseded by [`REBUILD_V3_PLAN.md`](./REBUILD_V3_PLAN.md).
> Do not extend the MCP-driven discovery/assembly path described below.

The frontend is the only source of truth for the non-secret OpenPencil profile: MCP
endpoint, component source file, output file, and creation mode. FastAPI owns the MCP bearer token, LLM
credentials, validation, workflow checkpoints, SQLite persistence, and SSE replay.

```text
React/Vite ── REST + SSE ── FastAPI ── ADK Workflow(LiteLlm)
    │                         │
    └── file/MCP profile      ├── SQLite runs/events/reviews
                              └── OpenPencil MCP ── independent .fig output
```

## Runtime flow

1. Persist the natural request and stream all state changes.
2. ADK produces a typed UI specification; pause for specification review.
3. Open the source `.fig`, inspect real components, and resolve exact bindings.
4. Save the source as an independent output, create a screen page, render JSX layout,
   and insert component instances.
5. Read geometry, perform layout review, save, and pause for final review.

The source file is never intentionally mutated. The external OpenPencil runtime limits
file access to its configured root; calls carry explicit document/page IDs. The
designer backend never supplies endpoint/path defaults. The workflow remains small
and deterministic in Python. ADK is used for structured reasoning rather than as a
second persistence engine.
