#!/usr/bin/env python3
import os, sys
import pandas as pd
import matplotlib.pyplot as plt

def read_tsv(path):
    if not os.path.exists(path):
        return None
    # mysql --batch outputs tab-separated with header row
    return pd.read_csv(path, sep="\t")

def ensure_report_dir(base):
    report = os.path.join(base, "report")
    os.makedirs(report, exist_ok=True)
    return report

def write_csv(df, outpath):
    df.to_csv(outpath, index=False)

def safe_num(s):
    return pd.to_numeric(s, errors="coerce")

def main(base):
    base = base.rstrip("/\\")
    if not os.path.isdir(base):
        print("Not a folder:", base)
        return 2

    report_dir = ensure_report_dir(base)

    # input files from baseline export
    events_tsv = os.path.join(base, "events.tsv")
    hourly_tsv = os.path.join(base, "hourly.tsv")
    zones_tsv  = os.path.join(base, "zones_summary.tsv")
    top_tsv    = os.path.join(base, "top_events.tsv")

    events = read_tsv(events_tsv)
    hourly = read_tsv(hourly_tsv)
    zones  = read_tsv(zones_tsv)
    top    = read_tsv(top_tsv)

    # TSV -> CSV
    if events is not None: write_csv(events, os.path.join(report_dir, "events.csv"))
    if hourly is not None: write_csv(hourly, os.path.join(report_dir, "hourly.csv"))
    if zones  is not None: write_csv(zones,  os.path.join(report_dir, "zones_summary.csv"))
    if top    is not None: write_csv(top,    os.path.join(report_dir, "top_events.csv"))

    # Dashboard figure
    fig, axes = plt.subplots(2, 2, figsize=(18, 10))
    fig.suptitle("iMouseGuard Baseline Dashboard", fontsize=16)

    # 1) Events per hour
    ax = axes[0, 0]
    if hourly is not None and {"hour","events"}.issubset(set(hourly.columns)):
        try:
            hourly["hour"] = pd.to_datetime(hourly["hour"], errors="coerce")
            hourly = hourly.dropna(subset=["hour"]).sort_values("hour")
            ax.plot(hourly["hour"], safe_num(hourly["events"]).fillna(0))
            ax.set_title("Events per Hour")
            ax.set_xlabel("Hour")
            ax.set_ylabel("Events")
            ax.tick_params(axis="x", rotation=45)
        except Exception:
            ax.text(0.5, 0.5, "hourly.tsv parse error", ha="center", va="center")
            ax.set_axis_off()
    else:
        ax.text(0.5, 0.5, "hourly.tsv missing", ha="center", va="center")
        ax.set_axis_off()

    # 2) Top zones by Count
    ax = axes[0, 1]
    if zones is not None and {"ZoneName","Count"}.issubset(set(zones.columns)):
        z = zones.copy()
        z["Count"] = safe_num(z["Count"]).fillna(0)
        topz = z.sort_values("Count", ascending=False).head(12)
        ax.bar(topz["ZoneName"].astype(str), topz["Count"])
        ax.set_title("Top Zones by Trigger Count")
        ax.set_xlabel("Zone")
        ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=35, labelsize=9)
    else:
        ax.text(0.5, 0.5, "zones_summary.tsv missing", ha="center", va="center")
        ax.set_axis_off()

    # 3) MaxScore distribution
    ax = axes[1, 0]
    if events is not None and "MaxScore" in events.columns:
        x = safe_num(events["MaxScore"]).dropna()
        ax.hist(x, bins=35)
        ax.set_title("MaxScore Distribution")
        ax.set_xlabel("MaxScore")
        ax.set_ylabel("Count")
    else:
        ax.text(0.5, 0.5, "events.tsv missing MaxScore", ha="center", va="center")
        ax.set_axis_off()

    # 4) AlarmFrames distribution
    ax = axes[1, 1]
    if events is not None and "AlarmFrames" in events.columns:
        x = safe_num(events["AlarmFrames"]).dropna()
        ax.hist(x, bins=35)
        ax.set_title("AlarmFrames Distribution")
        ax.set_xlabel("AlarmFrames")
        ax.set_ylabel("Count")
    else:
        ax.text(0.5, 0.5, "events.tsv missing AlarmFrames", ha="center", va="center")
        ax.set_axis_off()

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    outpng = os.path.join(report_dir, "dashboard.png")
    plt.savefig(outpng, dpi=150)
    plt.close(fig)

    # quick terminal summary
    print("\n=== Baseline Summary ===")
    print("Folder:", base)
    if events is not None:
        print("Events:", len(events))
        if "MonitorId" in events.columns:
            vc = events["MonitorId"].value_counts().head(10)
            print("Top monitors:\n", vc.to_string())
    if zones is not None and {"ZoneName","Count"}.issubset(set(zones.columns)):
        topz = zones.sort_values("Count", ascending=False).head(10)[["ZoneName","Count"]]
        print("\nTop zones:\n", topz.to_string(index=False))

    print("\nSaved CSVs + dashboard:", report_dir)
    print("Dashboard:", outpng)
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: imouse_analyze.py /path/to/baseline_folder")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
