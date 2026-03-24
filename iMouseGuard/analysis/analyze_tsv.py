#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import pandas as pd


TSV_LAYOUT = {
    "events.tsv": {
        "columns": [
            "EventId",
            "MonitorId",
            "StartDateTime",
            "EndDateTime",
            "Length",
            "AlarmFrames",
            "AvgScore",
            "MaxScore",
            "TotScore",
            "Cause",
            "Notes",
        ],
        "aliases": {
            "StartTime": "StartDateTime",
            "EndTime": "EndDateTime",
            "Frames": "TotScore",
        },
    },
    "hourly.tsv": {
        "columns": [
            "MonitorId",
            "hour",
            "events",
            "avg_maxscore",
            "peak_maxscore",
            "total_alarm_frames",
        ],
        "aliases": {},
    },
    "zones_summary.tsv": {
        "columns": [
            "MonitorId",
            "ZoneName",
            "stat_rows",
            "avg_score",
            "peak_score",
            "avg_alarm_pixels",
            "avg_blobs",
        ],
        "aliases": {},
    },
    "top_events.tsv": {
        "columns": [
            "EventId",
            "MonitorId",
            "StartDateTime",
            "Length",
            "AlarmFrames",
            "MaxScore",
            "AvgScore",
            "TotScore",
            "Notes",
        ],
        "aliases": {},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze iMouseGuard baseline TSV exports and generate graphs."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Folder containing events.tsv, hourly.tsv, zones_summary.tsv, top_events.tsv",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output folder for normalized CSV, charts, and summary (default: analysis/results/<input_folder>)",
    )
    return parser.parse_args()


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _first_row_values(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        first = handle.readline().strip("\r\n")
    return first.split("\t") if first else []


def _is_header_row(first_row: List[str], expected: List[str], aliases: Dict[str, str]) -> bool:
    if len(first_row) != len(expected):
        return False
    canonical = [aliases.get(col.strip(), col.strip()) for col in first_row]
    if canonical == expected:
        return True
    expected_set = set(expected)
    return all(col in expected_set for col in canonical)


def read_tsv(path: Path, expected: List[str], aliases: Dict[str, str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=expected)

    first_row = _first_row_values(path)
    has_header = _is_header_row(first_row, expected, aliases)

    if has_header:
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    else:
        df = pd.read_csv(
            path,
            sep="\t",
            header=None,
            names=expected,
            dtype=str,
            keep_default_na=False,
        )

    df.columns = [str(col).strip() for col in df.columns]
    rename_map = {src: dst for src, dst in aliases.items() if src in df.columns}
    if rename_map:
        df = df.rename(columns=rename_map)

    for col in expected:
        if col not in df.columns:
            df[col] = pd.NA

    return df[expected]


def _empty_panel(ax, title: str, message: str) -> None:
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.set_axis_off()


def _prepare_hourly(hourly: pd.DataFrame) -> pd.DataFrame:
    if hourly.empty:
        return pd.DataFrame()
    work = hourly.copy()
    work["hour"] = pd.to_datetime(work["hour"], errors="coerce")
    work["events"] = to_num(work["events"])
    work["avg_maxscore"] = to_num(work["avg_maxscore"])
    work["peak_maxscore"] = to_num(work["peak_maxscore"])
    work["total_alarm_frames"] = to_num(work["total_alarm_frames"])
    work = work.dropna(subset=["hour"])
    if work.empty:
        return pd.DataFrame()
    return (
        work.groupby("hour", as_index=False)
        .agg(
            events=("events", "sum"),
            avg_maxscore=("avg_maxscore", "mean"),
            peak_maxscore=("peak_maxscore", "max"),
            total_alarm_frames=("total_alarm_frames", "sum"),
        )
        .sort_values("hour")
    )


def _score_source(events: pd.DataFrame, top_events: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if not events.empty:
        return events, "events.tsv"
    if not top_events.empty:
        return top_events, "top_events.tsv"
    return pd.DataFrame(), "no data"


def write_normalized_tables(output_dir: Path, tables: Dict[str, pd.DataFrame]) -> None:
    for filename, df in tables.items():
        csv_name = filename.replace(".tsv", "_normalized.csv")
        df.to_csv(output_dir / csv_name, index=False)


def save_hourly_chart(output_dir: Path, hourly_agg: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    if hourly_agg.empty:
        _empty_panel(ax, "Hourly Events", "No hourly data")
    else:
        ax.plot(hourly_agg["hour"], hourly_agg["events"], marker="o", linewidth=1.7)
        ax.set_title("Events per Hour")
        ax.set_xlabel("Hour")
        ax.set_ylabel("Events")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(output_dir / "hourly_events.png", dpi=150)
    plt.close(fig)


def save_zones_chart(output_dir: Path, zones: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    if zones.empty:
        _empty_panel(ax, "Zone Activity", "No zone summary data")
    else:
        work = zones.copy()
        work["stat_rows"] = to_num(work["stat_rows"])
        top = (
            work.groupby("ZoneName", as_index=False)["stat_rows"]
            .sum()
            .sort_values("stat_rows", ascending=False)
            .head(12)
        )
        if top.empty:
            _empty_panel(ax, "Zone Activity", "No usable zone rows")
        else:
            ax.barh(top["ZoneName"], top["stat_rows"])
            ax.invert_yaxis()
            ax.set_title("Top Zones by Trigger Rows")
            ax.set_xlabel("Trigger Rows")
            ax.set_ylabel("Zone")
            ax.grid(alpha=0.25, axis="x", linestyle="--")
    fig.tight_layout()
    fig.savefig(output_dir / "zones_activity.png", dpi=150)
    plt.close(fig)


def save_top_scatter(output_dir: Path, top_events: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    if top_events.empty:
        _empty_panel(ax, "Top Events Scatter", "No top events data")
    else:
        work = top_events.copy()
        work["AlarmFrames"] = to_num(work["AlarmFrames"])
        work["MaxScore"] = to_num(work["MaxScore"])
        points = work.dropna(subset=["AlarmFrames", "MaxScore"])
        if points.empty:
            _empty_panel(ax, "Top Events Scatter", "No numeric rows")
        else:
            ax.scatter(points["AlarmFrames"], points["MaxScore"], alpha=0.75)
            ax.set_title("Top Events: AlarmFrames vs MaxScore")
            ax.set_xlabel("AlarmFrames")
            ax.set_ylabel("MaxScore")
            ax.grid(alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(output_dir / "top_events_scatter.png", dpi=150)
    plt.close(fig)


def save_score_histograms(output_dir: Path, events: pd.DataFrame, top_events: pd.DataFrame) -> None:
    source, source_name = _score_source(events, top_events)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    if source.empty:
        _empty_panel(axes[0], "MaxScore Distribution", "No event score data")
        _empty_panel(axes[1], "AlarmFrames Distribution", "No alarm frames data")
    else:
        max_scores = to_num(source["MaxScore"]).dropna()
        alarms = to_num(source["AlarmFrames"]).dropna()

        if max_scores.empty:
            _empty_panel(axes[0], "MaxScore Distribution", f"No numeric MaxScore in {source_name}")
        else:
            axes[0].hist(max_scores, bins=20, edgecolor="black")
            axes[0].set_title(f"MaxScore Distribution ({source_name})")
            axes[0].set_xlabel("MaxScore")
            axes[0].set_ylabel("Count")

        if alarms.empty:
            _empty_panel(
                axes[1], "AlarmFrames Distribution", f"No numeric AlarmFrames in {source_name}"
            )
        else:
            axes[1].hist(alarms, bins=20, edgecolor="black")
            axes[1].set_title(f"AlarmFrames Distribution ({source_name})")
            axes[1].set_xlabel("AlarmFrames")
            axes[1].set_ylabel("Count")

    fig.tight_layout()
    fig.savefig(output_dir / "score_distributions.png", dpi=150)
    plt.close(fig)


def save_dashboard(
    output_dir: Path,
    hourly_agg: pd.DataFrame,
    zones: pd.DataFrame,
    events: pd.DataFrame,
    top_events: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(18, 9))
    fig.suptitle("iMouseGuard TSV Analysis Dashboard", fontsize=15)

    if hourly_agg.empty:
        _empty_panel(axes[0, 0], "Events per Hour", "No hourly data")
        _empty_panel(axes[0, 1], "Hourly Scores", "No hourly data")
    else:
        axes[0, 0].plot(hourly_agg["hour"], hourly_agg["events"], marker="o", linewidth=1.5)
        axes[0, 0].set_title("Events per Hour")
        axes[0, 0].set_xlabel("Hour")
        axes[0, 0].set_ylabel("Events")
        axes[0, 0].tick_params(axis="x", rotation=45)
        axes[0, 0].grid(alpha=0.2, linestyle="--")

        axes[0, 1].plot(
            hourly_agg["hour"], hourly_agg["avg_maxscore"], label="Avg MaxScore", linewidth=1.5
        )
        axes[0, 1].plot(
            hourly_agg["hour"], hourly_agg["peak_maxscore"], label="Peak MaxScore", linewidth=1.5
        )
        axes[0, 1].set_title("Hourly MaxScore Trend")
        axes[0, 1].set_xlabel("Hour")
        axes[0, 1].set_ylabel("Score")
        axes[0, 1].tick_params(axis="x", rotation=45)
        axes[0, 1].legend()
        axes[0, 1].grid(alpha=0.2, linestyle="--")

    if zones.empty:
        _empty_panel(axes[0, 2], "Zones by Trigger Rows", "No zone summary data")
    else:
        work = zones.copy()
        work["stat_rows"] = to_num(work["stat_rows"])
        top = (
            work.groupby("ZoneName", as_index=False)["stat_rows"]
            .sum()
            .sort_values("stat_rows", ascending=False)
            .head(10)
        )
        if top.empty:
            _empty_panel(axes[0, 2], "Zones by Trigger Rows", "No numeric zone rows")
        else:
            axes[0, 2].barh(top["ZoneName"], top["stat_rows"])
            axes[0, 2].invert_yaxis()
            axes[0, 2].set_title("Zones by Trigger Rows")
            axes[0, 2].set_xlabel("Rows")
            axes[0, 2].set_ylabel("Zone")

    if top_events.empty:
        _empty_panel(axes[1, 0], "Top Events Scatter", "No top event data")
    else:
        scatter = top_events.copy()
        scatter["AlarmFrames"] = to_num(scatter["AlarmFrames"])
        scatter["MaxScore"] = to_num(scatter["MaxScore"])
        scatter = scatter.dropna(subset=["AlarmFrames", "MaxScore"])
        if scatter.empty:
            _empty_panel(axes[1, 0], "Top Events Scatter", "No numeric top event rows")
        else:
            axes[1, 0].scatter(scatter["AlarmFrames"], scatter["MaxScore"], alpha=0.75)
            axes[1, 0].set_title("AlarmFrames vs MaxScore")
            axes[1, 0].set_xlabel("AlarmFrames")
            axes[1, 0].set_ylabel("MaxScore")
            axes[1, 0].grid(alpha=0.2, linestyle="--")

    score_df, source_name = _score_source(events, top_events)
    if score_df.empty:
        _empty_panel(axes[1, 1], "MaxScore Distribution", "No score source data")
        _empty_panel(axes[1, 2], "AlarmFrames Distribution", "No score source data")
    else:
        max_scores = to_num(score_df["MaxScore"]).dropna()
        alarms = to_num(score_df["AlarmFrames"]).dropna()

        if max_scores.empty:
            _empty_panel(axes[1, 1], "MaxScore Distribution", f"No numeric MaxScore in {source_name}")
        else:
            axes[1, 1].hist(max_scores, bins=20, edgecolor="black")
            axes[1, 1].set_title(f"MaxScore Distribution ({source_name})")
            axes[1, 1].set_xlabel("MaxScore")
            axes[1, 1].set_ylabel("Count")

        if alarms.empty:
            _empty_panel(
                axes[1, 2], "AlarmFrames Distribution", f"No numeric AlarmFrames in {source_name}"
            )
        else:
            axes[1, 2].hist(alarms, bins=20, edgecolor="black")
            axes[1, 2].set_title(f"AlarmFrames Distribution ({source_name})")
            axes[1, 2].set_xlabel("AlarmFrames")
            axes[1, 2].set_ylabel("Count")

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(output_dir / "dashboard.png", dpi=160)
    plt.close(fig)


def write_summary(
    output_dir: Path,
    input_dir: Path,
    events: pd.DataFrame,
    hourly_agg: pd.DataFrame,
    zones: pd.DataFrame,
    top_events: pd.DataFrame,
) -> None:
    lines: List[str] = []
    lines.append("iMouseGuard TSV Analysis Summary")
    lines.append("=" * 34)
    lines.append(f"Input folder: {input_dir}")
    lines.append(f"Output folder: {output_dir}")
    lines.append("")
    lines.append("Row Counts:")
    lines.append(f"- events.tsv rows: {len(events)}")
    lines.append(f"- hourly.tsv rows: {len(hourly_agg)}")
    lines.append(f"- zones_summary.tsv rows: {len(zones)}")
    lines.append(f"- top_events.tsv rows: {len(top_events)}")
    lines.append("")

    if not hourly_agg.empty:
        total_events = int(hourly_agg["events"].fillna(0).sum())
        lines.append(f"Total events from hourly aggregation: {total_events}")
        peak = hourly_agg.sort_values("events", ascending=False).head(1)
        if not peak.empty:
            peak_hour = peak.iloc[0]["hour"]
            peak_count = int(peak.iloc[0]["events"])
            lines.append(f"Peak hour: {peak_hour} ({peak_count} events)")
        lines.append(
            f"Average hourly MaxScore: {hourly_agg['avg_maxscore'].mean(skipna=True):.2f}"
        )
        lines.append(f"Peak hourly MaxScore: {hourly_agg['peak_maxscore'].max(skipna=True):.2f}")
    else:
        lines.append("No usable hourly data.")

    lines.append("")
    if not zones.empty:
        work = zones.copy()
        work["stat_rows"] = to_num(work["stat_rows"])
        top_zone = (
            work.groupby("ZoneName", as_index=False)["stat_rows"]
            .sum()
            .sort_values("stat_rows", ascending=False)
            .head(1)
        )
        if not top_zone.empty:
            lines.append(
                f"Top zone by trigger rows: {top_zone.iloc[0]['ZoneName']} ({int(top_zone.iloc[0]['stat_rows'])})"
            )
    else:
        lines.append("No zone summary data.")

    if not top_events.empty:
        work = top_events.copy()
        work["MaxScore"] = to_num(work["MaxScore"])
        best = work.sort_values("MaxScore", ascending=False).head(1)
        if not best.empty and pd.notna(best.iloc[0]["MaxScore"]):
            lines.append(
                f"Top event by MaxScore: EventId {best.iloc[0]['EventId']} (MaxScore {int(best.iloc[0]['MaxScore'])})"
            )
    else:
        lines.append("No top events data.")

    (output_dir / "analysis_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def run(input_dir: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    tables: Dict[str, pd.DataFrame] = {}
    for filename, cfg in TSV_LAYOUT.items():
        table = read_tsv(input_dir / filename, cfg["columns"], cfg["aliases"])
        tables[filename] = table

    events = tables["events.tsv"]
    hourly = tables["hourly.tsv"]
    zones = tables["zones_summary.tsv"]
    top_events = tables["top_events.tsv"]

    hourly_agg = _prepare_hourly(hourly)

    write_normalized_tables(output_dir, tables)
    save_hourly_chart(output_dir, hourly_agg)
    save_zones_chart(output_dir, zones)
    save_top_scatter(output_dir, top_events)
    save_score_histograms(output_dir, events, top_events)
    save_dashboard(output_dir, hourly_agg, zones, events, top_events)
    write_summary(output_dir, input_dir, events, hourly_agg, zones, top_events)

    print("Analysis complete.")
    print(f"Input : {input_dir}")
    print(f"Output: {output_dir}")
    print("Generated files:")
    for path in sorted(output_dir.glob("*")):
        print(f"- {path.name}")
    return 0


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"Input folder not found: {input_dir}")
        return 2

    if args.output:
        output_dir = Path(args.output).expanduser().resolve()
    else:
        output_dir = Path(__file__).resolve().parent / "results" / input_dir.name

    return run(input_dir, output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
