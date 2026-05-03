OPENAI_API_KEY ?= $(shell echo $$OPENAI_API_KEY)
PHOTOS        ?= photos
OUTPUT        ?= flowers.json

.PHONY: update-flowers reset-progress serve help

## Run GPT-4o identification + Firestore cleanup (always run together)
update-flowers:
	python3 identify.py --photos $(PHOTOS) --output $(OUTPUT)
	python3 reset_progress.py --flowers $(OUTPUT)

## Only prune stale Firestore entries (e.g. after manually editing flowers.json)
reset-progress:
	python3 reset_progress.py --flowers $(OUTPUT)

## Start local dev server
serve:
	python3 -m http.server 8080

help:
	@echo "make update-flowers   — re-identify all flowers + sync Firestore"
	@echo "make reset-progress   — prune Firestore without re-identifying"
	@echo "make serve            — start local server on :8080"
