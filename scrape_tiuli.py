#!/usr/bin/env python3
"""
Scrape tiuli.com/flora for Jerusalem-area wildflowers.
Outputs tiuli_seed.json with: tiuli_id, name_he, name_en, sci_name, family, bloom_months.

Usage:
    uv run python scrape_tiuli.py
    uv run python scrape_tiuli.py --limit 10   # test run
"""
import argparse
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE      = "https://www.tiuli.com"
LIST_URL  = f"{BASE}/flora"
HEADERS   = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Hebrew family names to skip (trees, grasses, shrubs without showy flowers)
SKIP_FAMILIES_HE = {
    "אורניים", "ברושיים",          # conifers
    "דגניים", "גמאיים", "שחמיים", # grasses / sedges / rushes
    "אשחריים",                      # tamarisk
    "תותיים", "אלמיים",            # figs, elms
    "צפצפתיים",                    # willows / poplars
}
KEEP_SCI = {"Rosa", "Sarcopoterium"}  # keep showy Rosaceae

# Hebrew month names → numbers
HE_MONTHS = {
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "אפריל": 4, "מאי": 5, "יוני": 6,
    "יולי": 7, "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
}


def get_soup(url: str, retries: int = 3) -> BeautifulSoup:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2)


def scrape_list_page(page: int) -> list[dict]:
    """Return list of {tiuli_id, name_he} from one list page."""
    soup = get_soup(f"{LIST_URL}?dests=3&page={page}")
    plants = []
    for a in soup.select("a[href*='/flora/']"):
        href = a.get("href", "")
        m = re.search(r"/flora/(\d+)/", href)
        if not m:
            continue
        tiuli_id = int(m.group(1))
        # Hebrew name is the text of the link or a child element
        name_he = a.get_text(strip=True)
        if name_he and tiuli_id:
            plants.append({"tiuli_id": tiuli_id, "name_he": name_he})
    # Deduplicate by id
    seen, unique = set(), []
    for p in plants:
        if p["tiuli_id"] not in seen:
            seen.add(p["tiuli_id"])
            unique.append(p)
    return unique


def scrape_plant_page(tiuli_id: int) -> dict:
    """Return {name_he, name_en, sci_name, family_he, bloom_months} from plant page."""
    soup = get_soup(f"{BASE}/flora/{tiuli_id}/")
    data = {}

    # Labels contain colon e.g. "משפחה:" followed by a sibling span with the value
    label_map = {
        "משפחה:":           "family_he",
        "שם לטיני:":        "sci_name",
        "שם עממי באנגלית:": "name_en",
    }
    for span in soup.find_all("span"):
        text = span.get_text(strip=True)
        if text in label_map:
            value_span = span.find_next_sibling("span")
            if value_span:
                data[label_map[text]] = value_span.get_text(strip=True)

    # Bloom months — look for Hebrew month names in the page
    months = []
    for he_month, num in HE_MONTHS.items():
        if soup.find(string=re.compile(he_month)):
            months.append(num)
    if months:
        data["bloom_months"] = sorted(set(months))

    return data


def should_skip(entry: dict) -> bool:
    if not entry.get("sci_name"):
        return True
    family_he = entry.get("family_he", "")
    sci       = entry.get("sci_name", "")
    genus     = sci.split()[0] if sci else ""
    if family_he in SKIP_FAMILIES_HE and genus not in KEEP_SCI:
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="tiuli_seed.json")
    parser.add_argument("--limit",  type=int, help="Max plants to process (for testing)")
    args = parser.parse_args()

    print("Step 1: collecting plant IDs from Jerusalem list pages...")
    all_plants, page = [], 1
    while True:
        try:
            batch = scrape_list_page(page)
        except Exception as e:
            print(f"  page {page} failed: {e}", file=sys.stderr)
            break
        if not batch:
            break
        all_plants.extend(batch)
        print(f"  page {page}: {len(batch)} plants (total {len(all_plants)})")
        # Check if there's a next page by seeing if we got a full batch
        if len(batch) < 10:
            break
        page += 1
        time.sleep(0.8)

    # Deduplicate
    seen, unique = set(), []
    for p in all_plants:
        if p["tiuli_id"] not in seen:
            seen.add(p["tiuli_id"])
            unique.append(p)
    all_plants = unique

    if args.limit:
        all_plants = all_plants[:args.limit]

    print(f"\nStep 2: fetching detail pages for {len(all_plants)} plants...")
    results = []
    skipped = 0
    for i, plant in enumerate(all_plants, 1):
        tid = plant["tiuli_id"]
        print(f"  [{i}/{len(all_plants)}] id={tid} {plant['name_he']}", end=" ... ", flush=True)
        try:
            detail = scrape_plant_page(tid)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        entry = {
            "tiuli_id":    tid,
            "name_he":     plant["name_he"],
            "name_en":     detail.get("name_en", ""),
            "sci_name":    detail.get("sci_name", ""),
            "family_he":   detail.get("family_he", ""),
            "bloom_months": detail.get("bloom_months", []),
        }

        if should_skip(entry):
            print(f"skip ({entry.get('family_he','?')})")
            skipped += 1
            continue

        results.append(entry)
        print(f"{entry['sci_name']} [{entry.get('family','?')}]")
        time.sleep(0.5)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone — {len(results)} wildflowers saved to {args.output} ({skipped} skipped)")


if __name__ == "__main__":
    main()
