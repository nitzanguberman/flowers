-include .env
export OPENAI_API_KEY
export ANTHROPIC_API_KEY
PHOTOS            ?= photos
OUTPUT            ?= flowers.json
COMPRESS           = for f in photos/*.jpeg photos/*.jpg; do [ -f "$$f" ] && sips -Z 1200 --setProperty formatOptions 80 "$$f" --out "$$f"; done

.PHONY: fetch-flowers update-flowers reset-progress serve help

## Build flowers.json from seed list — fetches iNaturalist photos + Claude metadata
fetch-flowers:
	uv run python fetch_flowers.py --seed flowers_seed.json --output $(OUTPUT) --photos-dir $(PHOTOS)
	$(COMPRESS)
	uv run python reset_progress.py --flowers $(OUTPUT)

## Legacy: re-identify from walk photos + sync Firestore
update-flowers:
	uv run python identify.py --photos $(PHOTOS) --output $(OUTPUT)
	$(COMPRESS)
	uv run python reset_progress.py --flowers $(OUTPUT)

## Only prune stale Firestore entries (after manually editing flowers.json)
reset-progress:
	uv run python reset_progress.py --flowers $(OUTPUT)

## Start local dev server
serve:
	uv run python -m http.server 8000

help:
	@echo "make fetch-flowers   — rebuild from seed list (new workflow)"
	@echo "make update-flowers  — re-identify from walk photos (legacy)"
	@echo "make reset-progress  — prune Firestore without re-identifying"
	@echo "make serve           — start local server on :8000"
