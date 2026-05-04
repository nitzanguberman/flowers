OPENAI_API_KEY    ?= $(shell echo $$OPENAI_API_KEY)
ANTHROPIC_API_KEY ?= $(shell echo $$ANTHROPIC_API_KEY)
PHOTOS            ?= photos
OUTPUT            ?= flowers.json
COMPRESS           = for f in photos/*.jpeg photos/*.jpg; do [ -f "$$f" ] && sips -Z 1200 --setProperty formatOptions 80 "$$f" --out "$$f"; done

.PHONY: fetch-flowers update-flowers reset-progress serve help

## Build flowers.json from seed list — fetches iNaturalist photos + Claude metadata
fetch-flowers:
	python3 fetch_flowers.py --seed flowers_seed.json --output $(OUTPUT) --photos-dir $(PHOTOS)
	$(COMPRESS)
	python3 reset_progress.py --flowers $(OUTPUT)

## Legacy: re-identify from walk photos + sync Firestore
update-flowers:
	python3 identify.py --photos $(PHOTOS) --output $(OUTPUT)
	$(COMPRESS)
	python3 reset_progress.py --flowers $(OUTPUT)

## Only prune stale Firestore entries (after manually editing flowers.json)
reset-progress:
	python3 reset_progress.py --flowers $(OUTPUT)

## Start local dev server
serve:
	python3 -m http.server 8000

help:
	@echo "make fetch-flowers   — rebuild from seed list (new workflow)"
	@echo "make update-flowers  — re-identify from walk photos (legacy)"
	@echo "make reset-progress  — prune Firestore without re-identifying"
	@echo "make serve           — start local server on :8000"
