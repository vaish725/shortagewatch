"""Freeze the analysis results into the repository so inference does not drift with live data.

Writes analysis/results/*.csv and manifest.json (run date, code commit, data versions). The dashboard's Insights page
reads these files, not the live warehouse. Run via `make analysis` after the models have been fitted.
"""
import json
import subprocess
from datetime import datetime, timezone

from analysis.common import ROOT, connect

OUT = ROOT / "analysis" / "results"
TABLES = ["model_results", "risk_points", "validation", "ingredient_match_precision", "duration_age_summary", "duration_km"]


def git(*args: str, cwd=ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def main(cutoff: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    try:
        for t in TABLES:
            con.sql(f"copy (select * from analysis.{t}) to '{OUT / (t + '.csv')}' (header, delimiter ',')")
        n_cases = con.sql("select max(n_cases) from analysis.model_results where model = 'primary'").fetchall()[0][0]
        snaps = con.sql("select max(dt)::varchar from stg_shortages").fetchall()[0][0]
    finally:
        con.close()
    manifest = {
        "analysis_run_date_utc": datetime.now(timezone.utc).date().isoformat(),
        "code_commit": git("rev-parse", "HEAD"),
        "code_tree_clean": git("status", "--porcelain", "--", "analysis", "warehouse", ":(exclude)analysis/results") == "",
        "data_snapshot_cutoff": cutoff,
        "latest_shortage_snapshot_used": snaps,
        "data_branch_commit": git("rev-parse", "HEAD", cwd=ROOT / "data-branch"),
        "primary_model_cases": int(n_cases),
        "plan": "docs/analysis_plan.md",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "none")
