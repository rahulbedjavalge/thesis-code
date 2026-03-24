# iMouseGuard TSV Analysis

This folder contains a reusable script to analyze baseline TSV exports and generate graphs.

## Input files

Put these 4 files in one folder:

- `events.tsv`
- `hourly.tsv`
- `zones_summary.tsv`
- `top_events.tsv`

## Run

From repo root:

```powershell
.venv\Scripts\python.exe iMouseGuard\analysis\analyze_tsv.py --input ".venv\2026-02-15_221452_last_24h_m_18"
```

Optional custom output directory:

```powershell
.venv\Scripts\python.exe iMouseGuard\analysis\analyze_tsv.py --input "<input_folder>" --output "iMouseGuard\analysis\results\my_run"
```

## Output

The script writes:

- normalized CSV copies for all 4 tables
- `hourly_events.png`
- `zones_activity.png`
- `top_events_scatter.png`
- `score_distributions.png`
- `dashboard.png`
- `analysis_summary.txt`
