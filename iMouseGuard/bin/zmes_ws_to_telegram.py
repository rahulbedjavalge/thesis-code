#!/usr/bin/env python3
import os
import json
import time
import subprocess
from websocket import create_connection

# ===========================
# CONFIG
# ===========================

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:9000")
HOOK = "/opt/iMouseGuard/iMouseGuard/bin/imouse_hook_alert.py"
DEBUG = os.getenv("IMOUSE_WS_DEBUG", "0") == "1"

# Monitor filter (comma separated: 18,19)
ALLOWED_MONITORS = os.getenv("IMOUSE_ALLOWED_MONITORS", "").strip()
ALLOWED_MONITOR_SET = {
    x.strip() for x in ALLOWED_MONITORS.split(",") if x.strip()
}

# Optional behavior filter (e.g. "zm_event,drinking_alert")
ALLOWED_BEHAVIORS = os.getenv("IMOUSE_ALLOWED_BEHAVIORS", "").strip()
ALLOWED_BEHAVIOR_SET = {
    x.strip() for x in ALLOWED_BEHAVIORS.split(",") if x.strip()
}

# ===========================
# UTILS
# ===========================

def log(*args):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "|", *args, flush=True)

def run_hook(eid, mid, payload):
    try:
        p = subprocess.Popen(
            [HOOK, str(eid), str(mid)],
            stdin=subprocess.PIPE
        )
        p.communicate(input=json.dumps(payload).encode("utf-8"), timeout=5)
    except Exception as e:
        log("hook error:", e)

def parse_events(data):
    out = []
    events = data.get("events") or data.get("Events") or []
    if isinstance(events, dict):
        events = [events]

    for obj in events:
        eid = (
            obj.get("EventId")
            or obj.get("event_id")
            or obj.get("eid")
        )

        mid = (
            obj.get("MonitorId")
            or obj.get("monitor_id")
            or obj.get("mid")
        )

        cause = obj.get("Cause") or obj.get("cause") or ""
        name = obj.get("Name") or obj.get("name") or ""

        if eid and mid:
            out.append({
                "eid": str(eid),
                "mid": str(mid),
                "cause": cause,
                "name": name
            })

    return out

# ===========================
# MAIN LOOP
# ===========================

def main():
    seen_eids = set()
    SEEN_MAX = 500

    while True:
        try:
            log("connecting to", WS_URL)
            ws = create_connection(WS_URL, timeout=5)
            ws.settimeout(300)

            # Authenticate (empty creds OK if auth disabled)
            ws.send(json.dumps({
                "event": "auth",
                "data": {"user": "", "password": ""}
            }))

            log("connected")

            # Subscribe (generic subscription)
            ws.send(json.dumps({
                "event": "filter",
                "data": {"monitors": "all"}
            }))

            while True:
                msg = ws.recv()
                if not msg:
                    continue

                if DEBUG:
                    log("recv:", msg[:300])

                try:
                    data = json.loads(msg)
                except Exception:
                    continue

                if str(data.get("event", "")).lower() == "auth":
                    continue

                for e in parse_events(data):
                    eid = e["eid"]
                    mid = e["mid"]

                    if not eid or eid == "0":
                        continue

                    if eid in seen_eids:
                        continue

                    # Monitor filter
                    if ALLOWED_MONITOR_SET and mid not in ALLOWED_MONITOR_SET:
                        if DEBUG:
                            log("skip monitor", mid)
                        continue

                    behavior = "zm_event"

                    # Behavior filter (optional)
                    if ALLOWED_BEHAVIOR_SET and behavior not in ALLOWED_BEHAVIOR_SET:
                        if DEBUG:
                            log("skip behavior", behavior)
                        continue

                    seen_eids.add(eid)
                    if len(seen_eids) > SEEN_MAX:
                        seen_eids.clear()

                    payload = {
                        "behavior": behavior,
                        "notes": e["cause"],
                        "monitor_name": e["name"]
                    }

                    log("forwarding event eid:", eid, "mid:", mid)
                    run_hook(eid, mid, payload)

        except Exception as e:
            log("ws error:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
