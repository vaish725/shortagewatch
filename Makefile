PY = .venv/bin/python

.PHONY: setup ingest test match data-sync transform quality

setup:
	python3 -m venv .venv
	$(PY) -m pip install -e ".[dev,warehouse]"

# Pull every source into data/raw/<source>/dt=<date>/
ingest:
	$(PY) -m ingestion.sources.shortages
	$(PY) -m ingestion.sources.enforcement
	$(PY) -m ingestion.sources.ndc
	$(PY) -m ingestion.sources.warning_letters

# Report recall-to-NDC match rates by method, on the same NDC snapshot dbt reads
match:
	NDC_SNAPSHOT_DIR=data-branch/snapshots/ndc $(PY) -m ingestion.recall_match

# Check out (or refresh) the data branch, where the dated snapshots live, into data-branch/
data-sync:
	if [ -d data-branch/.git ]; then git -C data-branch pull -q --ff-only; \
	else git clone -q --branch data --single-branch --depth 1 "$$(git remote get-url origin)" data-branch; fi

# Build and test the warehouse (needs data-sync, ingest for recalls, and match for the parity test)
transform:
	cd warehouse && ../$(PY) -m dbt.cli.main build

# Print the live data quality metrics
quality:
	cd warehouse && ../$(PY) -c "import duckdb; [print(r) for r in duckdb.connect('target/shortagewatch.duckdb', read_only=True).sql('select * from mart_data_quality order by area, metric').fetchall()]"

test:
	$(PY) -m pytest -q
