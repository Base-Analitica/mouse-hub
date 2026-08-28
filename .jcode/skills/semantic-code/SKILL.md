---
name: semantic-code
description: Use local Serena for symbol overviews, symbol lookup and references before reading large Python source files; use it only when semantic navigation helps.
---

# Semantic code

This project uses a small read-only bridge to the official Serena MCP server (Python project). Pinned, project-local dependencies, stdio only — no global MCP registration, no ports.

Run `scripts/agent/semantic-code tools` as a health check. If missing, run `scripts/agent/bootstrap-serena` once (requires `uv`). Useful queries:

- `scripts/agent/semantic-code overview <path>`
- `scripts/agent/semantic-code find <name> --path <path> [--body]`
- `scripts/agent/semantic-code refs <name> <path>`
- `scripts/agent/semantic-code diagnostics <path>`

Use the agent's native editing and exact reads for changes and non-code files. Keep answers bounded with `--max-chars`; fall back to `rg` and native tools if Serena fails.
