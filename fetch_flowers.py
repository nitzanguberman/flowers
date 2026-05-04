#!/usr/bin/env python3
"""
List-driven flower data pipeline.
Reads a seed list of species, fetches high-quality iNaturalist photos from Israel,
generates Hebrew metadata via Claude, and writes flowers.json.

Usage:
    python3 fetch_flowers.py --seed flowers_seed.json --output flowers.json --photos-dir photos
    python3 fetch_flowers.py --seed flowers_seed.json --limit 5   # test run
"""
import argparse
import json
import os
import re
import sys
import time

import anthropic
import requests
from dotenv import load_dotenv
load_dotenv()

INAT_OBSERVATIONS = "https://api.inaturalist.org/v1/observations"
INAT_TAXA         = "https://api.inaturalist.org/v1/taxa"
ISRAEL_PLACE_ID   = 6986
HEADERS           = {"User-Agent": "FlowersGame/2.0"}


def sci_name_to_slug(sci_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", sci_name.lower()).strip("_")


def to_large_url(url: str) -> str:
    """Convert any iNaturalist size variant to large."""
    return re.sub(r"/(square|small|medium|thumb)\.(jpe?g|png)", r"/large.\2", url)


def fetch_photo_url_from_observations(sci_name: str) -> str | None:
    """Best research-grade Israel observation photo (large size)."""
    try:
        r = requests.get(INAT_OBSERVATIONS, headers=HEADERS, timeout=15, params={
            "taxon_name": sci_name,
            "place_id": ISRAEL_PLACE_ID,
            "quality_grade": "research",
            "photos": "true",
            "order_by": "votes",
            "per_page": 5,
        })
        for obs in r.json().get("results", []):
            for photo in obs.get("photos", []):
                url = photo.get("url", "")
                if url:
                    return to_large_url(url)
    except Exception as e:
        print(f"    [observations API error] {e}", file=sys.stderr)
    return None


def fetch_photo_url_from_taxa(sci_name: str) -> str | None:
    """Fallback: iNaturalist taxon default photo."""
    try:
        r = requests.get(INAT_TAXA, headers=HEADERS, timeout=15, params={
            "q": sci_name, "is_active": "true", "per_page": 1,
        })
        results = r.json().get("results", [])
        if results:
            dp = results[0].get("default_photo") or {}
            return dp.get("large_url") or dp.get("medium_url")
    except Exception as e:
        print(f"    [taxa API error] {e}", file=sys.stderr)
    return None


def download_photo(url: str, dest_path: str) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    [download error] {e}", file=sys.stderr)
        return False


def generate_metadata(client: anthropic.Anthropic, sci_name: str, name_en: str, name_he: str | None) -> dict:
    """Call Claude Haiku to generate name_he (if missing) and info (always)."""
    if name_he:
        prompt = (
            f"Flower: {name_en} ({sci_name})\n"
            f"Hebrew name: {name_he}\n\n"
            "Return ONLY a JSON object with one key:\n"
            '- "info": 1-2 sentences in Hebrew about this flower\'s habitat, bloom season, '
            "and one interesting fact. Use standard Israeli Hebrew.\n\n"
            "Return only the JSON, no markdown."
        )
    else:
        prompt = (
            f"Flower: {name_en} ({sci_name})\n\n"
            "Return ONLY a JSON object with two keys:\n"
            '- "name_he": the standard Israeli botanical Hebrew name (not a translation)\n'
            '- "info": 1-2 sentences in Hebrew about habitat, bloom season, and one interesting fact\n\n'
            "Return only the JSON, no markdown."
        )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception as e:
        print(f"    [Claude error] {e}", file=sys.stderr)
        return {}


def main():
    parser = argparse.ArgumentParser(description="Build flowers.json from a species seed list")
    parser.add_argument("--seed",       default="flowers_seed.json", help="Input seed JSON file")
    parser.add_argument("--output",     default="flowers.json",      help="Output flowers.json")
    parser.add_argument("--photos-dir", default="photos",            help="Directory for downloaded photos")
    parser.add_argument("--limit",      type=int,                    help="Process only N species (testing)")
    parser.add_argument("--api-key",    default=os.environ.get("ANTHROPIC_API_KEY"), help="Anthropic API key")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: set ANTHROPIC_API_KEY or pass --api-key", file=sys.stderr)
        sys.exit(1)

    with open(args.seed, encoding="utf-8") as f:
        seed = json.load(f)

    if args.limit:
        seed = seed[:args.limit]

    # Load existing output to allow resuming interrupted runs
    existing = {}
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            for entry in json.load(f):
                existing[entry.get("sci_name", "")] = entry

    client = anthropic.Anthropic(api_key=args.api_key)
    results = []

    for i, species in enumerate(seed, 1):
        sci_name = species["sci_name"]
        name_en  = species["name_en"]
        name_he  = species.get("name_he")

        print(f"[{i}/{len(seed)}] {sci_name}", end=" ... ", flush=True)

        # Resume: skip if already done
        if sci_name in existing:
            print("(cached)")
            results.append(existing[sci_name])
            continue

        # 1. Fetch photo URL
        photo_url = fetch_photo_url_from_observations(sci_name)
        source = "observations"
        if not photo_url:
            photo_url = fetch_photo_url_from_taxa(sci_name)
            source = "taxa"
        if not photo_url:
            print("NO PHOTO — skipping")
            continue

        # 2. Download photo
        slug      = sci_name_to_slug(sci_name)
        ext       = "jpeg" if ".jpeg" in photo_url else "jpg"
        filename  = f"inat_{slug}.{ext}"
        dest_path = os.path.join(args.photos_dir, filename)
        if not download_photo(photo_url, dest_path):
            print("DOWNLOAD FAILED — skipping")
            continue

        # 3. Generate Hebrew metadata via Claude
        meta    = generate_metadata(client, sci_name, name_en, name_he)
        name_he = name_he or meta.get("name_he", name_en)
        info    = meta.get("info", "")

        entry = {
            "file":      os.path.join("photos", filename),
            "name_en":   name_en,
            "name_he":   name_he,
            "sci_name":  sci_name,
            "info":      info,
            "photo_url": photo_url,
        }
        results.append(entry)
        print(f"{name_he}  [{source}]")

        # Save after each entry so partial runs are recoverable
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(0.5)  # be polite to iNaturalist

    print(f"\nDone — {len(results)} flowers saved to {args.output}")


if __name__ == "__main__":
    main()
