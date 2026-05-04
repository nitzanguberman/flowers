# Flowers Game

Hebrew flower identification game with Leitner-box spaced repetition, multiple flower collections, and Firebase-backed cross-device progress.

Live game: https://nitzanguberman.github.io/flowers/game/

## Agent Notes

Read `CLAUDE.md` before changing workflow. It is the source of truth for branch strategy, deployment, and GitHub publishing preferences.

Current branch policy:

- `main`: production. GitHub Pages serves this branch from the repo root.
- `develop`: active development. Normal work should land here first, then merge to `main`.
- Do not commit directly to `main` unless the user explicitly asks for a production deploy.

GitHub publishing:

- Preferred workflow is GitHub MCP `push_files`, not direct `git push`.
- The project was configured in Codex with a `github` MCP server in `~/.codex/config.toml`; restart Codex if MCP tools are not available in the active session.
- If the user explicitly permits direct push, keep pushes narrowly scoped and avoid including unrelated local files.

Python encapsulation:

- Use the project environment. Prefer `uv`.
- Run Python scripts with `uv run python <script.py>`.
- Add packages with `uv add <package>`.
- Refresh dependencies with `uv sync`.
- Do not run `pip install` globally and do not use bare system Python for project tooling unless there is no project dependency involved.

Dirty worktree expectations:

- Untracked local files may exist. Do not delete or commit them unless the user asks.
- Check status before staging.
- Stage exact files, not broad patterns.

## Local Development

Serve from the repo root so `game/` can fetch data and photos with relative paths:

```bash
uv run python -m http.server 8000
```

Open:

```text
http://localhost:8000/game/
```

For this mostly static app, there is no build step.

## Structure

- `game/index.html`: main app, UI, game logic, Firebase calls.
- `game/firebase-config.js`: Firebase config imported by the app.
- `collections.json`: collection picker metadata.
- `flowers_walks.json`: smaller personal/walks collection.
- `flowers_top30.json`: common Jerusalem flowers collection.
- `flowers2.json`: large Jerusalem collection.
- `photos/`: local photos for the smaller collection.
- `photos_tiuli/`: local photos for the larger Tiuli collection, tracked with Git LFS.

Flower records generally include:

```json
{
  "file": "photos/example.jpeg",
  "name_en": "English name",
  "name_he": "שם עברי",
  "sci_name": "Species name",
  "info": "Short Hebrew description",
  "photo_url": "https://..."
}
```

The game should prefer local `file` images and fall back to `photo_url` when a local asset is missing or unavailable.

## Deployment

Normal deployment path:

```bash
git checkout main
git merge develop
# publish via GitHub MCP, or direct git push only if explicitly approved
git checkout develop
```

GitHub Pages usually updates within about a minute after `main` changes.

## Verification

Before pushing to `main`:

- Run a local static server from the repo root.
- Open `/game/`.
- Pick a user and collection.
- Verify a question renders with a flower image and answer choices.
- Check that the browser is not showing broken-image icons.

