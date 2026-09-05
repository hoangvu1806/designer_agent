# OpenPencil integration decision

> **Superseded on 2026-09-03.** See [`REBUILD_V3_PLAN.md`](./REBUILD_V3_PLAN.md). OpenPencil MCP is
> now a display/review adapter only. Source discovery, component extraction, compilation, save,
> and deterministic validation are performed headlessly from `.fig` files.

Date: 2026-09-01  
Status: adopted for the greenfield implementation

## Decision

Replace Penpot with OpenPencil. Use Streamable HTTP MCP for design writes and the
headless CLI for optional file inspection, linting, overlap checks, exports, and CI.
The React frontend owns the non-secret connection profile; the MCP auth token remains
in the FastAPI `.env` and is never persisted in browser storage.

## Why

OpenPencil reads and writes `.fig` and `.pen`, exposes `open_file`, `new_document`,
`render`, component, layout, export, and `save_file` tools, and accepts explicit
`document_id`/`page_id`. This removes the Penpot plugin's dependency on the user
keeping the exact target file focused.

There is one important boundary: official MCP documentation says automation runs
through the running OpenPencil app. The CLI is the fully file-headless path. We do
not claim MCP writes work with no OpenPencil runtime.

## File strategy

The currently released component model is safest inside one document. Cross-document
published libraries are visible in the upstream unreleased changelog and are not a
stable dependency yet. Therefore:

1. Open the source design-system `.fig` without modifying it.
2. Save it as a new output `.fig` under `OPENPENCIL_MCP_ROOT`.
3. Create and switch to a new screen page in that output copy.
4. Discover local components, resolve bindings, render the flexible layout with JSX,
   and insert real component instances.
5. Measure page bounds, save the output, and request final human review.

The source remains unchanged; each generated artifact is a normal, portable file.
When stable cross-document library APIs ship, the gateway can change without altering
the workflow or UI specification contracts.

For the browser/Vite runtime, `open_file` transfers file bytes from the MCP server to
the browser bridge instead of asking the browser to fetch a Windows disk path. This
allows a saved `.fig` under the MCP root to open even when it is not already visible
in an OpenPencil tab. The source file must still exist on disk; the offline knowledge
catalog cannot replace the real component vectors.

## Security and reliability

- Bind HTTP MCP to loopback and keep authentication enabled.
- Scope all file operations with `OPENPENCIL_MCP_ROOT`; never accept unrestricted paths.
- Pass explicit target IDs instead of relying on the visible tab.
- Treat missing tools, empty discovery, invalid JSON, timeout, and save failures as
  blocked/failed states—never synthetic success.
- Use CLI lint/overlap analysis as a later deterministic layout gate; LLM review remains
  semantic, not the only geometric validator.

## Sources reviewed

- OpenPencil repository and README: https://github.com/open-pencil/open-pencil
- MCP server documentation: https://openpencil.dev/programmable/mcp-server
- JSX renderer documentation: https://openpencil.dev/programmable/jsx-renderer
- MCP registration source: https://github.com/open-pencil/open-pencil/blob/master/packages/mcp/src/tool/registration.ts
- Component tool source: https://github.com/open-pencil/open-pencil/blob/master/packages/core/src/tools/read/components.ts
- Changelog and current library roadmap: https://github.com/open-pencil/open-pencil/blob/master/CHANGELOG.md
- Community issues: https://github.com/open-pencil/open-pencil/issues
