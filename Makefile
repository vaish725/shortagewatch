PY = .venv/bin/python

.PHONY: setup ingest test match

setup:
	python3 -m venv .venv
	$(PY) -m pip install -e ".[dev]"

# Pull every source into data/raw/<source>/dt=<date>/
ingest:
	$(PY) -m ingestion.sources.shortages
	$(PY) -m ingestion.sources.enforcement
	$(PY) -m ingestion.sources.ndc
	$(PY) -m ingestion.sources.warning_letters

# Report recall-to-NDC match rates by method
match:
	$(PY) -m ingestion.recall_match

test:
	$(PY) -m pytest -q
