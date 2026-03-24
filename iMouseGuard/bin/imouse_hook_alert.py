#!/usr/bin/env python3
"""
iMouseGuard - Alert hook (enriched)

Reads JSON on stdin and argv:
  argv[1] = Event ID (eid)
  argv[2] = Monitor ID (mid)

Builds an alert message and sends to:
- Telegram
- Slack
- WhatsApp (Twilio) if enabled

Zone enrichment:
- Primary: DB lookup from ZoneMinder Stats + Zones tables (fast + reliable)
- Fallback: Parse Zone from "Cause" string if present (often empty in WS mode)
"""

import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# Import rules engine for behavioral detection
try:
    from . import rules_engine
    HAS_RULES_ENGINE = True
except:
    try:
        import rules_engine
        HAS_RULES_ENGINE = True
    except:
        HAS_RULES_ENGINE = False

# ---------- config ----------
# Optional env files (useful for local dev). On server we rely on real env vars from `.env`.
ENV_FILES = (
    "/opt/iMouseGuard/iMouseGuard/.env",          # server
    "/opt/iMouseGuard/iMouseGuard/prod.env",      # optional if you use
    # "D:\\iMouseGuard\\iMouseGuard\\env\\prod.env",  # local Windows (keep only if you really need it)
)

# WhatsApp cooldown to avoid Twilio 429 spam
# Example: 120 seconds means max 1 WA message every 2 min
WA_COOLDOWN_SECONDS_DEFAULT = 120
WA_COOLDOWN_STATE_FILE = "/opt/iMouseGuard/iMouseGuard/logs/whatsapp_last_sent.txt"


# ---------- utils ----------
def _clean(val: str) -> str:
    if val is None:
        return ""
    v = str(val).strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        v = v[1:-1]
    return v.replace("\r", "").replace("\n", "").strip()


def get_env(name: str, default: str = "") -> str:
    v = os.getenv(name, None)
    if v:
        return _clean(v)

    # fallback: read from env files
    for path in ENV_FILES:
        try:
            if not path or not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # supports: export KEY=VAL
                    if line.startswith(f"export {name}="):
                        return _clean(line.split("=", 1)[1])
                    # supports: KEY=VAL
                    if line.startswith(f"{name}="):
                        return _clean(line.split("=", 1)[1])
        except Exception:
            pass

    return default


def log_err(msg: str) -> None:
    print(f"[HOOK] {msg}", file=sys.stderr, flush=True)


def log_info(msg: str) -> None:
    print(f"[HOOK] {msg}", flush=True)


def http_get_json(url: str, timeout: int = 4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                log_err(f"HTTP {resp.status} for {url}")
                return None
            payload = resp.read().decode("utf-8", "ignore")
            return json.loads(payload)
    except Exception as e:
        log_err(f"GET failed {url}: {e}")
        return None


# ---------- Zone enrichment (DB) ----------
def get_event_top_zone(eid: str) -> str:
    """
    Returns a single best zone line like:
      "Zone: Drinking (Score 97)"
    or "" if not found.
    """
    if not eid:
        return ""

    host = get_env("MYSQL_HOST", "db").strip()
    user = get_env("MYSQL_USER", "").strip()
    pw = get_env("MYSQL_PASSWORD", "").strip()
    db = get_env("ZM_DB_NAME", "zm").strip()
    min_score = int(get_env("ZONE_MIN_SCORE", "1"))

    if not (host and user and pw and db):
        return ""

    try:
        eid_int = int(eid)
    except Exception:
        return ""

    sql = f"""
SELECT z.Name, s.Score
FROM Stats s
JOIN Zones z ON z.Id=s.ZoneId
WHERE s.EventId={eid_int}
ORDER BY s.Score DESC
LIMIT 1;
""".strip()

    try:
        cmd = ["mysql", "-h", host, "-u", user, f"-p{pw}", db, "-N", "-e", sql]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=3).decode("utf-8", "ignore").strip()
        if not out:
            return ""
        name, score = out.split("\t")[:2]
        if int(score) < min_score:
            return ""
        return f"Zone: {name} (Score {score})"
    except Exception as e:
        log_err(f"zone lookup failed: {e}")
        return ""


def guess_zone_from_cause(cause: str) -> str:
    # Fallback only
    if not cause:
        return ""
    parts = [p.strip() for p in cause.split(":")]
    if len(parts) >= 2:
        return parts[1]
    return ""


# ---------- enrichment (API, optional) ----------
def fetch_event(eid: str):
    base = get_env("IMOUSE_API_BASE", "http://127.0.0.1")
    url = f"{base}/api/events/view/{eid}.json"
    j = http_get_json(url)
    if not j or "event" not in j:
        return {}
    ev = j["event"]["Event"]
    return {
        "Name": ev.get("Name"),
        "Cause": ev.get("Cause"),
        "Start": ev.get("StartDateTime"),
        "End": ev.get("EndDateTime"),
        "Length": ev.get("Length"),
        "TotScore": ev.get("TotScore"),
        "MaxScore": ev.get("MaxScore"),
        "MonitorId": str(ev.get("MonitorId") or ""),
    }


def fetch_monitor_name(mid: str) -> str:
    if not mid:
        return ""
    base = get_env("IMOUSE_API_BASE", "http://127.0.0.1")
    url = f"{base}/api/monitors/view/{mid}.json"
    j = http_get_json(url)
    try:
        return j["monitor"]["Monitor"]["Name"]
    except Exception:
        return ""


def event_link(eid: str) -> str:
    web = get_env("IMOUSE_WEB_BASE", "http://127.0.0.1")
    return f"{web}/index.php?view=event&eid={eid}"


# ---------- senders ----------
def send_telegram(text: str, retries: int = 2) -> None:
    token = get_env("TELEGRAM_TOKEN")
    chat = get_env("TELEGRAM_CHAT_ID")
    thread = get_env("TELEGRAM_THREAD_ID")
    if not token or not chat:
        log_err("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat, "text": text}
    if thread:
        params["message_thread_id"] = thread
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})

    backoff = 0.7
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    log_err(f"Telegram HTTP {resp.status}")
                else:
                    log_info("[TELEGRAM] sent ok")
                return
        except Exception as e:
            if attempt >= retries:
                log_err(f"Telegram send failed: {e}")
                return
            time.sleep(backoff)
            backoff *= 2


def send_slack(text: str, retries: int = 2) -> None:
    webhook = get_env("SLACK_WEBHOOK_URL").strip()
    if not webhook:
        log_err("SLACK_WEBHOOK_URL missing")
        return
    if not webhook.startswith("https://hooks.slack.com/services/"):
        log_err("SLACK_WEBHOOK_URL looks invalid (must start with https://hooks.slack.com/services/...)")
        return

    payload = json.dumps({"text": text}).encode("utf-8")
    backoff = 0.7

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                webhook,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8", "ignore").strip()
                if resp.status == 200 and (body == "" or body.lower() == "ok"):
                    log_info("[SLACK] sent ok")
                    return
                log_err(f"[SLACK] HTTP {resp.status}, body={body}")
                return
        except Exception as e:
            if attempt >= retries:
                log_err(f"[SLACK] send failed: {e}")
                return
            time.sleep(backoff)
            backoff *= 2


def _wa_cooldown_ok() -> bool:
    try:
        cooldown = int(get_env("WA_COOLDOWN_SECONDS", str(WA_COOLDOWN_SECONDS_DEFAULT)))
    except Exception:
        cooldown = WA_COOLDOWN_SECONDS_DEFAULT

    try:
        if not os.path.exists(WA_COOLDOWN_STATE_FILE):
            return True
        last = int(open(WA_COOLDOWN_STATE_FILE, "r").read().strip() or "0")
        return (int(time.time()) - last) >= cooldown
    except Exception:
        return True


def _wa_mark_sent() -> None:
    try:
        os.makedirs(os.path.dirname(WA_COOLDOWN_STATE_FILE), exist_ok=True)
        with open(WA_COOLDOWN_STATE_FILE, "w") as f:
            f.write(str(int(time.time())))
    except Exception:
        pass


def send_whatsapp(text: str, retries: int = 2) -> None:
    enabled = get_env("WHATSAPP_ENABLED").lower() in ("1", "true", "yes", "on")
    if not enabled:
        return

    if not _wa_cooldown_ok():
        log_err("[WHATSAPP] skipped due to cooldown")
        return

    sid = get_env("TWILIO_ACCOUNT_SID")
    token = get_env("TWILIO_AUTH_TOKEN")
    wa_from = get_env("WHATSAPP_FROM")
    wa_to = get_env("WHATSAPP_TO")

    if not sid or not token or not wa_from or not wa_to:
        log_err("WhatsApp missing env: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / WHATSAPP_FROM / WHATSAPP_TO")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}

    recipients = [r.strip() for r in wa_to.split(",") if r.strip()]
    if not recipients:
        log_err("WHATSAPP_TO is empty")
        return

    backoff = 0.7
    sent_any = False

    for to in recipients:
        data = urllib.parse.urlencode({"From": wa_from, "To": to, "Body": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read().decode("utf-8", "ignore").strip()
                    if 200 <= resp.status < 300:
                        log_info(f"[WHATSAPP] sent ok to {to}")
                        sent_any = True
                        break
                    log_err(f"[WHATSAPP] HTTP {resp.status} to {to}, body={body}")
                    break
            except Exception as e:
                if attempt >= retries:
                    log_err(f"[WHATSAPP] send failed to {to}: {e}")
                    break
                time.sleep(backoff)
                backoff *= 2

    if sent_any:
        _wa_mark_sent()


# ---------- main ----------
def main() -> int:
    raw = sys.stdin.read().strip()
    eid = sys.argv[1] if len(sys.argv) > 1 else ""
    mid = sys.argv[2] if len(sys.argv) > 2 else ""

    body = {}
    if raw:
        try:
            body = json.loads(raw)
        except Exception:
            body = {}

    behavior = str(body.get("behavior", "") or "zm_event")
    notes = str(body.get("notes", "") or "")

    # API enrichment is optional; keep off unless you need it
    # ev = fetch_event(eid) if eid else {}
    # mon_name = fetch_monitor_name(mid) if mid else ""
    ev = {}
    mon_name = ""

    # zone from DB (primary), or from cause string (fallback)
    zone_line = get_event_top_zone(eid) if eid else ""
    cause = ev.get("Cause") or notes
    if not zone_line:
        z = guess_zone_from_cause(cause)
        if z:
            zone_line = f"Zone: {z}"

    lines = ["🐭 iMouse Alert"]
    if mon_name:
        lines.append(f"Monitor: {mid} ({mon_name})")
    elif mid:
        lines.append(f"Monitor: {mid}")

    if eid:
        lines.append(f"Event ID: {eid}")

    if behavior:
        lines.append(f"Behavior: {behavior}")

    if zone_line:
        lines.append(zone_line)

    if cause:
        lines.append(f"Cause: {cause}")

    if ev.get("Start"):
        lines.append(f"Start: {ev['Start']}")
    if ev.get("Length"):
        lines.append(f"Length: {ev['Length']}s")
    if ev.get("MaxScore") is not None:
        lines.append(f"Max score: {ev['MaxScore']}")

    if eid:
        lines.append(f"View: {event_link(eid)}")

    msg = "\n".join(lines)

    # one-line log for debugging
    log_info(f"event={eid} monitor={mid} behavior={behavior} {zone_line}")

    # ========== RULES ENGINE EVALUATION ==========
    if HAS_RULES_ENGINE:
        # Build event for rules engine
        event = {
            "event_id": int(eid) if eid else 0,
            "monitor_id": int(mid) if mid else 0,
            "zone_id": int(body.get("zone_id", 0) or 0),
            "score": int(body.get("score", 0) or 0),
            "behavior": behavior,
            "severity": body.get("severity", "INFO"),
            "timestamp": time.time()
        }
        
        # Evaluate behavioral rules
        rule_result = rules_engine.evaluate_rules(event)
        
        if rule_result:
            # Add rule information to message
            rule_msg = f"\n\n🎯 RULE TRIGGERED: {rule_result['rule']}\n"
            rule_msg += f"📊 {rule_result['message']}"
            msg += rule_msg
            log_info(f"RULE={rule_result['rule']} severity={rule_result.get('severity', 'INFO')}")

    # ========== SEND ALERTS ==========
    send_telegram(msg)
    send_slack(msg)
    send_whatsapp(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
