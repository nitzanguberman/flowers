#!/usr/bin/env python3
"""
Reset user flower progress in Firestore.
Run this whenever flowers.json changes (flowers added or removed).

Uses the Firestore REST API with the Firebase web API key — no service account needed.

Usage:
  python3 reset_progress.py
  python3 reset_progress.py --dry-run
"""
import argparse
import json
import os
import requests
from dotenv import load_dotenv
load_dotenv()

PROJECT_ID = "flowers-game-5e085"
API_KEY    = os.environ["FIREBASE_API_KEY"]
BASE_URL   = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"


def fs_get(path):
    r = requests.get(f"{BASE_URL}/{path}", params={"key": API_KEY})
    r.raise_for_status()
    return r.json()


def fs_patch(path, fields):
    """Update specific fields on a document."""
    body = {"fields": fields}
    field_paths = "&".join(f"updateMask.fieldPaths={k}" for k in fields)
    r = requests.patch(
        f"{BASE_URL}/{path}?{field_paths}&key={API_KEY}",
        json=body,
    )
    r.raise_for_status()
    return r.json()


def parse_value(v):
    """Parse a Firestore value dict into a Python value."""
    if "stringValue" in v:  return v["stringValue"]
    if "integerValue" in v: return int(v["integerValue"])
    if "doubleValue" in v:  return v["doubleValue"]
    if "booleanValue" in v: return v["booleanValue"]
    if "mapValue" in v:
        return {k: parse_value(vv) for k, vv in v["mapValue"]["fields"].items()}
    return None


def encode_value(v):
    """Encode a Python value into a Firestore value dict."""
    if isinstance(v, bool):  return {"booleanValue": v}
    if isinstance(v, int):   return {"integerValue": str(v)}
    if isinstance(v, float): return {"doubleValue": v}
    if isinstance(v, str):   return {"stringValue": v}
    if isinstance(v, dict):
        return {"mapValue": {"fields": {k: encode_value(vv) for k, vv in v.items()}}}
    return {"nullValue": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flowers", default="flowers.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    flowers = json.load(open(args.flowers, encoding="utf-8"))
    valid_files = {f["file"] for f in flowers}
    print(f"Current flowers.json: {len(valid_files)} flowers\n")

    # List all users
    data = fs_get("users")
    docs = data.get("documents", [])
    print(f"Found {len(docs)} users in Firestore\n")

    for doc in docs:
        name = doc["name"].split("/")[-1]
        fields = doc.get("fields", {})
        session_count = parse_value(fields.get("sessionCount", {"integerValue": "0"}))
        flower_map = parse_value(fields.get("flowers", {"mapValue": {"fields": {}}})) or {}

        stale = [f for f in flower_map if f not in valid_files]

        print(f"👤 {name}  (סשנים: {session_count}, פרחים: {len(flower_map)})")
        if stale:
            print(f"   מסיר {len(stale)} פרחים ישנים:")
            for f in stale:
                print(f"   ✂  {f}")
        else:
            print(f"   ✅ הכל תקין")

        if stale and not args.dry_run:
            for f in stale:
                del flower_map[f]
            fs_patch(
                f"users/{name}",
                {"flowers": encode_value(flower_map)},
            )
            print(f"   💾 עודכן")
        print()

    if args.dry_run:
        print("Dry run — לא בוצעו שינויים.")
    else:
        print("סיום.")


if __name__ == "__main__":
    main()
