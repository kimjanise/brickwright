# Brickwright Studio

A ChatGPT-style chat interface for creating custom LEGO builds, with conversation history, follow-up revisions, interactive 3D models, LDraw downloads, and live LEGO Pick a Brick prices.

## Run locally

From the repository root:

```sh
uv sync --all-packages --all-extras --group dev
npm --prefix web ci
npm --prefix web run build
codex login
uv run --all-extras uvicorn brickwright.web.app:app --host 127.0.0.1 --port 8818
```

Open http://127.0.0.1:8818. Install the official Codex CLI first if it is not on your PATH. Build generation uses the account signed into Codex and its usage limits. No API key is required for ChatGPT login. The built frontend is included in the Python package; rebuilding is only necessary after changing the frontend source.

Describe a build, wait for validation, then rotate the model or download its LDraw file. Send another message to revise the last successful build. **Check price** queries LEGO for the selected market. Partial quotes are labeled; shipping, service fees, and additional checkout taxes are excluded.

The preview uses bundled part geometry, so a full LDraw library is not required. For development, run `npm --prefix web run dev`; Vite proxies API requests to port 8818.

## Runtime and persistence

Use one server worker. Conversations are scoped to an HTTP-only browser cookie and stored under `.web-data/` (override with `BRICKWRIGHT_WEB_DATA`). Keep this directory private and out of Git. Clearing the cookie loses browser access to its history. Deleting a conversation removes its history; record files remain on disk for local recovery.

Each generation creates a record; revisions fork the previous successful record. A queued background job invokes `codex exec --sandbox workspace-write` in a session workspace, validates the generated model through Brickwright, and finalizes the LDraw export. Only finalized models are shown. A failed or cancelled revision leaves previous builds intact. Jobs run serially, with a five-job queue and a 15-minute limit. Stop terminates the child process group. Restarting the server marks interrupted jobs as failed so the UI does not spin forever.

This is a **local studio**, not an Internet-ready multiuser service. It binds to loopback, checks the Host and Origin headers, and uses same-site session cookies. Do not expose it through a public proxy. A public service requires authentication, durable job execution, per-user quotas, and isolated workers with restricted credentials and filesystem access; do not reuse a host user's Codex session for anonymous visitors.

## Checks

```sh
uv run --all-extras pytest
uv run ruff check packages/brickwright/src/brickwright/web packages/brickwright/tests/web
uv run ty check packages/brickwright/src/brickwright/web
npm --prefix web run build
```
