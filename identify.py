#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import requests
from openai import OpenAI

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

SYSTEM_PROMPT = """You are a expert botanist specializing in Israeli and Mediterranean flora.
Your job is to identify flowers from photos and return structured data."""

USER_PROMPT = """Identify the flower in this photo. Return ONLY a JSON object with these fields:
- name_en: common English name
- name_he: Hebrew name (use the standard Israeli botanical Hebrew name, not a translation)
- sci_name: scientific (Latin) name
- info: one or two sentences describing this flower in Hebrew (habitat, bloom season, interesting facts)

If you cannot identify the flower with reasonable confidence, return {"error": "cannot identify"}.
Return only the JSON, no markdown, no explanation."""

INAT_URL = "https://api.inaturalist.org/v1/taxa"
HEADERS  = {"User-Agent": "FlowersGame/1.0"}


def encode_image(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def identify_with_gpt(client, photo_path):
    ext = os.path.splitext(photo_path)[1].lower()
    media_type = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
    b64 = encode_image(photo_path)

    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:{media_type};base64,{b64}"}},
                {"type": "text", "text": USER_PROMPT},
            ]},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def fetch_inat_photo(sci_name):
    """Fetch reference photo URL from iNaturalist for a scientific name."""
    try:
        r = requests.get(INAT_URL, headers=HEADERS, timeout=10,
            params={"q": sci_name, "is_active": "true", "per_page": 1})
        results = r.json().get("results", [])
        if not results:
            return None
        return (results[0].get("default_photo") or {}).get("medium_url")
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Identify flowers using Claude vision")
    parser.add_argument("--photos", required=True, help="Path to folder with flower photos")
    parser.add_argument("--output", default="flowers.json", help="Output JSON file")
    parser.add_argument("--limit", type=int, default=None, help="Only process N photos (for testing)")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"), help="OpenAI API key")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: set OPENAI_API_KEY or pass --api-key", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=args.api_key)

    photos_dir = os.path.expanduser(args.photos)
    all_files = sorted(f for f in os.listdir(photos_dir)
                       if os.path.splitext(f)[1].lower() in IMAGE_EXTS)
    files = all_files[:args.limit] if args.limit else all_files

    if not files:
        print(f"No images found in {photos_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} photos. Identifying with Claude vision...")
    results = []

    for i, filename in enumerate(files, 1):
        path = os.path.join(photos_dir, filename)
        rel_path = os.path.join("photos", filename)
        print(f"  [{i}/{len(files)}] {filename} ...", end=" ", flush=True)

        try:
            data = identify_with_gpt(client, path)
            if "error" in data:
                print("could not identify, skipping")
                continue

            name_en  = data.get("name_en", "")
            name_he  = data.get("name_he", name_en)
            sci_name = data.get("sci_name", "")
            info     = data.get("info", "")

            print(f"{name_en} / {name_he}")

            photo_url = fetch_inat_photo(sci_name) if sci_name else None

            entry = {"file": rel_path, "name_en": name_en, "name_he": name_he,
                     "sci_name": sci_name}
            if info:
                entry["info"] = info
            if photo_url:
                entry["photo_url"] = photo_url
            results.append(entry)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"parse error: {e}", file=sys.stderr)
        except Exception as e:
            print(f"API error: {e}", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(results)} flowers to {args.output}")


if __name__ == "__main__":
    main()
