"""Render the latest run summaries (data/runs/) as a markdown table for the GitHub job summary.

Run: .venv/bin/python -m ingestion.run_summary
"""
import json

from ingestion.utils.storage import RUNS_ROOT


def render() -> str:
    days = sorted(RUNS_ROOT.glob("dt=*"))
    if not days:
        return "No run summaries found."
    lines = [f"### Pipeline run {days[-1].name[3:]}", "", "| Step | Detail |", "|---|---|"]
    for f in sorted(days[-1].glob("*.json")):
        s = json.loads(f.read_text())
        if s["step"] == "recall_match":
            detail = (f"{s['match_rate']:.1%} of {s['recalls']} recalls matched ({s['product_level_rate']:.1%} to a product); "
                      f"last 24 months: {s['window_match_rate']:.1%}")
        else:
            detail = f"{s['landed']} records landed, {s['quarantined']} quarantined"
        lines.append(f"| {s['step']} | {detail} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
