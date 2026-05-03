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

## Local Development

```bash
# From repo root:
python3 -m http.server 8000
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

The repo belongs to `nitzanguberman` but the macOS keychain stores `nitzang_mobileye` credentials for github.com, which causes 403 errors on plain `git push`. Use the token explicitly:

```bash
TOKEN=$(security find-internet-password -s github.com -a nitzanguberman -w 2>/dev/null)
git remote set-url origin "https://${TOKEN}@github.com/nitzanguberman/flowers.git"
git push
git remote set-url origin https://github.com/nitzanguberman/flowers.git
```

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
