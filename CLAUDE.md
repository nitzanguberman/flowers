# Flowers Game

A Hebrew flower identification game with spaced repetition (Leitner boxes) and cross-device progress sync.

## Live URL

https://nitzanguberman.github.io/flowers/game/

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production — GitHub Pages serves from here. Merge from `develop` to deploy. |
| `develop` | Active development. Work here, test locally, then PR → `main`. |

Never commit directly to `main`.

## Setup (first time)

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv

# Install Python dependencies into the project venv
uv sync
```

## Python Tooling Rules

This project uses **uv** for Python environment management.

- **Never** run `pip install` or `python3 <script>` directly.
- **Always** use `uv run python <script>` to run scripts (the Makefile already does this).
- **Always** use `uv add <package>` to add new dependencies — this updates `pyproject.toml` and `uv.lock`.
- **Always** use `uv sync` to install or refresh the environment.

## Local Development

```bash
# From repo root:
uv run python -m http.server 8000
# or simply: make serve
# Open: http://localhost:8000/game/
```

The game fetches `../flowers.json` and `../photos/` relative to `game/`, so serving from the repo root works as-is.

## Deploying

```bash
git checkout main
git merge develop
git push   # GitHub Pages auto-deploys within ~1 min
git checkout develop
```

## Pushing to GitHub

**Always use the GitHub MCP server — never `git push` directly.**

The macOS keychain stores `nitzang_mobileye` credentials for github.com, so plain `git push` always fails with 403. The MCP server (`~/.claude/.mcp.json`) is configured with the correct `nitzanguberman` token and loads automatically.

### Push workflow
1. `git add && git commit` locally (preserves local history)
2. Use MCP `push_files` tool to publish to GitHub:
   - `owner`: `nitzanguberman`, `repo`: `flowers`
   - `branch`: `develop` (or `main` for production deploys)
   - `files`: array of `{ path, content }` for every changed file
   - `message`: commit message
3. Sync local SHA to remote: `git fetch && git reset --hard origin/<branch>`

If MCP tools aren't available, restart the Claude Code session (MCP loads on startup via `enableAllProjectMcpServers: true` in `~/.claude/settings.json`).

## Stack

- **Frontend**: Single HTML file (`game/index.html`) — no build step, vanilla JS ES modules
- **Data**: `flowers.json` — array of flower objects with Hebrew/English names, photo path, iNaturalist URL
- **Photos**: `photos/` — compressed JPEGs (max 1200px, quality 80), ~24MB total
- **Backend**: Firebase Firestore (`flowers-game-5e085`) — stores per-user spaced repetition state
- **Hosting**: GitHub Pages from `main` branch root

## Firebase

Project: `flowers-game-5e085` (Firestore, `europe-west1`)

User data stored at `users/{username}` with this shape:
```json
{
  "sessionCount": 5,
  "flowers": {
    "photos/IMG_xxx.jpeg": { "box": 2, "lastSession": 3, "correct": 5, "total": 7 }
  }
}
```

Firestore rules must allow open read/write (no auth — login is by username only):
```
match /users/{username} { allow read, write: if true; }
```

## Adding Flowers

Run `identify.py` locally (not committed — local dev tool). It adds entries to `flowers.json` and downloads photos to `photos/`. After running, compress new photos:

```bash
for f in photos/*.jpeg; do sips -Z 1200 --setProperty formatOptions 80 "$f" --out "$f"; done
for f in photos/*.jpg;  do sips -Z 1200 --setProperty formatOptions 80 "$f" --out "$f"; done
```

Then commit `flowers.json` and `photos/` to `develop`.
