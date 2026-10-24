PY = .venv/bin/python

.PHONY: setup ingest test match data-sync transform quality analysis dashboard

setup:
	python3 -m venv .venv
	$(PY) -m pip install -e ".[dev,warehouse,analysis]"

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

# Rebuild the frozen analysis (docs/analysis_plan.md): rebuilds the warehouse as of ANALYSIS_CUTOFF, fits the models,
# and writes analysis/results/ with a manifest of the date, code commit and data versions. CI never refits; run this
# deliberately, commit analysis/results/ and warehouse/seeds/, then run `make transform` to restore the live warehouse.
ANALYSIS_CUTOFF ?= 2026-10-22
analysis:
	cd warehouse && ../$(PY) -m dbt.cli.main seed --full-refresh --vars '{snapshot_cutoff: "$(ANALYSIS_CUTOFF)"}'
	cd warehouse && ../$(PY) -m dbt.cli.main run --vars '{snapshot_cutoff: "$(ANALYSIS_CUTOFF)"}'
	$(PY) -m analysis.precision
	$(PY) -m analysis.risk_factors
	$(PY) -m analysis.duration
	$(PY) -m analysis.risk_score
	$(PY) -m analysis.freeze $(ANALYSIS_CUTOFF)

# Build the static dashboard from the warehouse (needs `make transform` and `make analysis`). Output: dashboard/build/
dashboard:
	$(PY) -m analysis.export_dashboard
	cd dashboard && npm ci --no-audit --no-fund && npm run sources && npm run build
