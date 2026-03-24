#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# iMouseGuard Baseline Collector
# -----------------------------
# Usage examples:
#   imouse_baseline.sh --last 24h --monitors 18
#   imouse_baseline.sh --last 6h --monitors 18,19,20
#   imouse_baseline.sh --last 2d --monitors all
#   imouse_baseline.sh --start "2026-02-15 08:00:00" --end "2026-02-15 12:00:00" --monitors 18
#
# Env needed (already in your .env):
#   MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, ZM_DB_NAME (default zm)

LAST=""
START=""
END=""
MONITORS="18"
OUTROOT="/opt/iMouseGuard/iMouseGuard/baselines"
DBNAME="${ZM_DB_NAME:-zm}"

die() { echo "[baseline] ERROR: $*" >&2; exit 1; }

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --last) LAST="${2:-}"; shift 2 ;;
    --start) START="${2:-}"; shift 2 ;;
    --end) END="${2:-}"; shift 2 ;;
    --monitors) MONITORS="${2:-}"; shift 2 ;;
    --out) OUTROOT="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '1,60p' "$0"
      exit 0
      ;;
    *) die "Unknown arg: $1" ;;
  esac
done

# validate timeframe
if [[ -n "$LAST" ]]; then
  # allow: 30m, 6h, 2d
  [[ "$LAST" =~ ^[0-9]+[mhd]$ ]] || die "--last must look like 30m / 6h / 2d"
fi

if [[ -n "$START" || -n "$END" ]]; then
  [[ -n "$START" && -n "$END" ]] || die "If using --start/--end, provide both"
fi

if [[ -z "$LAST" && -z "$START" ]]; then
  LAST="24h"
fi

# require mysql env
: "${MYSQL_HOST:?Missing MYSQL_HOST}"
: "${MYSQL_USER:?Missing MYSQL_USER}"
: "${MYSQL_PASSWORD:?Missing MYSQL_PASSWORD}"

# build time filter SQL
TIME_SQL=""
RANGE_LABEL=""
if [[ -n "$LAST" ]]; then
  n="${LAST%[mhd]}"; u="${LAST: -1}"
  case "$u" in
    m) TIME_SQL="e.StartDateTime >= (NOW() - INTERVAL ${n} MINUTE)";;
    h) TIME_SQL="e.StartDateTime >= (NOW() - INTERVAL ${n} HOUR)";;
    d) TIME_SQL="e.StartDateTime >= (NOW() - INTERVAL ${n} DAY)";;
  esac
  RANGE_LABEL="last_${LAST}"
else
  TIME_SQL="e.StartDateTime >= '${START}' AND e.StartDateTime <= '${END}'"
  RANGE_LABEL="$(echo "${START}_to_${END}" | tr ' :' '__' | tr -cd 'A-Za-z0-9_')"
fi

# monitor filter SQL + label
MON_SQL=""
MON_LABEL=""
if [[ "${MONITORS,,}" == "all" ]]; then
  MON_SQL="1=1"
  MON_LABEL="all"
else
  # turn "18,19,20" into "18,19,20"
  MON_LIST="$(echo "$MONITORS" | tr -d ' ' )"
  [[ "$MON_LIST" =~ ^[0-9]+(,[0-9]+)*$ ]] || die "--monitors must be like 18 or 18,19,20 or all"
  MON_SQL="e.MonitorId IN (${MON_LIST})"
  MON_LABEL="m_${MON_LIST}"
fi

TS="$(date +%F_%H%M%S)"
OUT="${OUTROOT}/${TS}_${RANGE_LABEL}_${MON_LABEL}"
mkdir -p "$OUT"

mysql_exec() {
  mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$DBNAME" -N -B -e "$1"
}

echo "[baseline] Writing to: $OUT"
echo "[baseline] DB: $DBNAME @ $MYSQL_HOST | monitors=$MONITORS | range=$RANGE_LABEL"

# -----------------------------
# 1) Core event table export
# -----------------------------
EVENTS_SQL="
SELECT
  e.Id AS EventId,
  e.MonitorId,
  e.StartDateTime,
  e.EndDateTime,
  e.Length,
  e.AlarmFrames,
  e.AvgScore,
  e.MaxScore,
  e.TotScore,
  e.Cause,
  e.Notes
FROM Events e
WHERE ${MON_SQL} AND (${TIME_SQL})
ORDER BY e.StartDateTime DESC;
"
mysql_exec "$EVENTS_SQL" > "$OUT/events.tsv"

# Count events
EVENT_COUNT="$(wc -l < "$OUT/events.tsv" | tr -d ' ')"

# If no events, still save diagnostics
if [[ "$EVENT_COUNT" == "0" ]]; then
  echo "[baseline] No events found for this filter."
  ps aux | egrep "zmeventnotification.pl|zmes_ws_to_telegram.py" | grep -v egrep > "$OUT/processes.txt" || true
  ss -ltnp | grep ":9000" > "$OUT/ports_9000.txt" || true
  exit 0
fi

# -----------------------------
# 2) Hourly summary per monitor
# -----------------------------
HOURLY_SQL="
SELECT
  e.MonitorId,
  DATE_FORMAT(e.StartDateTime, '%Y-%m-%d %H:00') AS hour,
  COUNT(*) AS events,
  ROUND(AVG(e.MaxScore),2) AS avg_maxscore,
  MAX(e.MaxScore) AS peak_maxscore,
  SUM(e.AlarmFrames) AS total_alarm_frames
FROM Events e
WHERE ${MON_SQL} AND (${TIME_SQL})
GROUP BY e.MonitorId, hour
ORDER BY hour DESC, e.MonitorId ASC;
"
mysql_exec "$HOURLY_SQL" > "$OUT/hourly.tsv"

# -----------------------------
# 3) Zone stats summary (Stats JOIN Zones)
#    This tells which zones really triggered.
# -----------------------------
ZONE_SUM_SQL="
SELECT
  e.MonitorId,
  z.Name AS ZoneName,
  COUNT(*) AS stat_rows,
  ROUND(AVG(s.Score),2) AS avg_score,
  MAX(s.Score) AS peak_score,
  ROUND(AVG(s.AlarmPixels),0) AS avg_alarm_pixels,
  ROUND(AVG(s.Blobs),2) AS avg_blobs
FROM Stats s
JOIN Zones z ON z.Id = s.ZoneId
JOIN Events e ON e.Id = s.EventId
WHERE ${MON_SQL} AND (${TIME_SQL})
GROUP BY e.MonitorId, z.Name
ORDER BY stat_rows DESC, peak_score DESC
LIMIT 200;
"
mysql_exec "$ZONE_SUM_SQL" > "$OUT/zones_summary.tsv"

# -----------------------------
# 4) Top events table (most "important")
# -----------------------------
TOP_SQL="
SELECT
  e.Id AS EventId,
  e.MonitorId,
  e.StartDateTime,
  e.Length,
  e.AlarmFrames,
  e.MaxScore,
  e.AvgScore,
  e.TotScore,
  e.Notes
FROM Events e
WHERE ${MON_SQL} AND (${TIME_SQL})
ORDER BY e.MaxScore DESC, e.AlarmFrames DESC
LIMIT 30;
"
mysql_exec "$TOP_SQL" > "$OUT/top_events.tsv"

# -----------------------------
# 5) Terminal analysis summary
# -----------------------------
echo ""
echo "================ iMouseGuard Baseline Summary ================"
echo "Output folder : $OUT"
echo "Monitors      : $MONITORS"
echo "Time range    : $RANGE_LABEL"
echo "Total events  : $EVENT_COUNT"
echo ""

echo "---- Events per monitor ----"
PER_MON_SQL="
SELECT e.MonitorId, COUNT(*) AS events,
       ROUND(AVG(e.MaxScore),2) AS avg_maxscore,
       MAX(e.MaxScore) AS peak_maxscore,
       ROUND(AVG(e.AlarmFrames),2) AS avg_alarm_frames
FROM Events e
WHERE ${MON_SQL} AND (${TIME_SQL})
GROUP BY e.MonitorId
ORDER BY events DESC;
"
mysql_exec "$PER_MON_SQL" | awk 'BEGIN{printf("%-10s %-10s %-12s %-12s %-16s\n","Monitor","Events","AvgMax","PeakMax","AvgAlarmFrames")} {printf("%-10s %-10s %-12s %-12s %-16s\n",$1,$2,$3,$4,$5)}'

echo ""
echo "---- Top zones by trigger frequency (per monitor) ----"
# show top 15 rows only in terminal, full saved in file
head -n 15 "$OUT/zones_summary.tsv" | awk 'BEGIN{printf("%-10s %-25s %-10s %-10s %-10s\n","Monitor","Zone","Rows","AvgScore","PeakScore")} {printf("%-10s %-25s %-10s %-10s %-10s\n",$1,$2,$3,$4,$5)}'

echo ""
echo "---- Top 10 events (by MaxScore) ----"
head -n 10 "$OUT/top_events.tsv" | awk 'BEGIN{printf("%-10s %-8s %-19s %-8s %-11s %-8s\n","EventId","Mon","Start","Max","AlarmFrames","Avg")} {printf("%-10s %-8s %-19s %-8s %-11s %-8s\n",$1,$2,$3,$6,$5,$7)}'

echo ""
echo "[baseline] Saved files:"
echo "  - events.tsv"
echo "  - hourly.tsv"
echo "  - zones_summary.tsv"
echo "  - top_events.tsv"
echo "=============================================================="
BASH