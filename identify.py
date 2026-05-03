#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import requests
from deep_translator import GoogleTranslator

PLANTNET_URL = "https://my-api.plantnet.org/v2/identify/all"
INAT_URL = "https://api.inaturalist.org/v1/taxa"
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def identify_plantnet(photo_path, api_key):
    with open(photo_path, "rb") as f:
        resp = requests.post(
            PLANTNET_URL,
            params={"api-key": api_key, "lang": "en"},
            files=[("images", (os.path.basename(photo_path), f, "image/jpeg"))],
            data={"organs": ["flower"]},
        )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None, None, None
    top = results[0]
    species = top.get("species", {})
    common_names = species.get("commonNames", [])
    name_en = common_names[0] if common_names else species.get("scientificNameWithoutAuthor", "")
    sci_name = species.get("scientificNameWithoutAuthor", "")
    score = top.get("score", 0)
    return name_en, sci_name, score


def lookup_inat(sci_name):
    """Return (hebrew_name, description) from iNaturalist, or (None, None)."""
    try:
        resp = requests.get(
            INAT_URL,
            params={"q": sci_name, "locale": "he", "is_active": "true", "per_page": 1},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None, None, None
        taxon = results[0]
        name_he = taxon.get("preferred_common_name") or None

        # wikipedia_summary requires a second call with the taxon ID
        taxon_id = taxon.get("id")
        photo_url = (taxon.get("default_photo") or {}).get("medium_url")
        desc = None
        if taxon_id:
            detail = requests.get(f"{INAT_URL}/{taxon_id}", timeout=10)
            detail.raise_for_status()
            detail_results = detail.json().get("results", [])
            if detail_results:
                raw = detail_results[0].get("wikipedia_summary") or ""
                if raw:
                    raw = re.sub(r"<[^>]+>", "", raw).strip()
                    desc = raw[:300].rsplit(" ", 1)[0] + "…" if len(raw) > 300 else raw

        return name_he, desc, photo_url
    except Exception:
        return None, None, None


def translate_to_hebrew(text):
    try:
        return GoogleTranslator(source="en", target="iw").translate(text)
    except Exception:
        return text


def main():
    parser = argparse.ArgumentParser(description="Identify flowers and produce flowers.json")
    parser.add_argument("--photos", required=True, help="Path to folder with flower photos")
    parser.add_argument("--key", required=True, help="PlantNet API key")
    parser.add_argument("--output", default="flowers.json", help="Output JSON file")
    parser.add_argument("--limit", type=int, default=None, help="Only process N photos (for testing)")
    args = parser.parse_args()

    photos_dir = os.path.expanduser(args.photos)
    all_files = sorted(
        f for f in os.listdir(photos_dir)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )
    files = all_files[:args.limit] if args.limit else all_files

    if not files:
        print(f"No images found in {photos_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} photos{' (limited)' if args.limit else ''}. Identifying...")
    results = []

    for i, filename in enumerate(files, 1):
        path = os.path.join(photos_dir, filename)
        rel_path = os.path.join("photos", filename)
        print(f"  [{i}/{len(files)}] {filename} ...", end=" ", flush=True)
        try:
            name_en, sci_name, score = identify_plantnet(path, args.key)
            if not name_en:
                print("no result, skipping")
                continue

            name_he, desc, photo_url = lookup_inat(sci_name)
            if not name_he:
                name_he = name_en
                source = "en-fallback"
            else:
                source = "iNat"

            print(f"{name_en} / {name_he} [{source}] (score: {score:.2f})")
            entry = {"file": rel_path, "name_en": name_en, "name_he": name_he}
            if desc:
                entry["info"] = desc
            if photo_url:
                entry["photo_url"] = photo_url
            results.append(entry)

        except requests.HTTPError as e:
            print(f"API error: {e}", file=sys.stderr)
            if e.response.status_code == 401:
                print("Invalid API key.", file=sys.stderr)
                sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(results)} flowers to {args.output}")


if __name__ == "__main__":
    main()
