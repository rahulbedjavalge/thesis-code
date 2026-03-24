#!/usr/bin/env python3
import os, sys, json, time, base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse, urllib.request

# ---------- env reading ----------
def _clean(val: str) -> str:
    if val is None:
        return ""
    v = str(val).strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        v = v[1:-1]
    return v.replace("\r", "").replace("\n", "").strip()

def load_env_file(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = _clean(v)
            os.environ[k] = v

def get_env(name: str) -> str:
    v = os.getenv(name, "")
    return _clean(v)

def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)

# ---------- senders ----------
def send_telegram(text: str) -> str:
    token = get_env("TELEGRAM_TOKEN")
    chat  = get_env("TELEGRAM_CHAT_ID")
    thread= get_env("TELEGRAM_THREAD_ID")

    if not token or not chat:
        return "SKIP (missing TELEGRAM_TOKEN/TELEGRAM_CHAT_ID)"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat, "text": text}
    if thread:
        params["message_thread_id"] = thread

    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return f"OK (HTTP {resp.status})"
    except Exception as e:
        return f"FAIL ({e})"

def send_slack(text: str) -> str:
    webhook = get_env("SLACK_WEBHOOK_URL").strip()
    if not webhook:
        return "SKIP (missing SLACK_WEBHOOK_URL)"

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", "ignore").strip()
            if resp.status == 200 and (body == "" or body.lower() == "ok"):
                return "OK (slack ok)"
            return f"FAIL (HTTP {resp.status}, body={body})"
    except Exception as e:
        return f"FAIL ({e})"

def send_whatsapp(text: str) -> str:
    enabled = (get_env("WHATSAPP_ENABLED") or get_env("ENABLE_WHATSAPP")).lower() in ("1", "true", "yes", "on")
    if not enabled:
        return "SKIP (WHATSAPP_ENABLED off/False)"

    sid   = get_env("TWILIO_ACCOUNT_SID")
    token = get_env("TWILIO_AUTH_TOKEN")
    wa_from = get_env("WHATSAPP_FROM")  # sandbox: whatsapp:+14155238886
    wa_to   = get_env("WHATSAPP_TO")    # whatsapp:+49...,whatsapp:+49...

    if not sid or not token or not wa_from or not wa_to:
        return f"SKIP (missing twilio env: sid={bool(sid)} token={bool(token)} from={bool(wa_from)} to={bool(wa_to)})"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    recipients = [r.strip() for r in wa_to.split(",") if r.strip()]
    if not recipients:
        return "SKIP (WHATSAPP_TO empty)"

    results = []
    for to in recipients:
        data = urllib.parse.urlencode({"From": wa_from, "To": to, "Body": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", "ignore")
                if 200 <= resp.status < 300:
                    results.append(f"OK->{to}")
                else:
                    results.append(f"FAIL->{to} (HTTP {resp.status}) {body[:120]}")
        except Exception as e:
            results.append(f"FAIL->{to} ({e})")
    return "; ".join(results)

# ---------- UI server ----------
HTML = """
<html>
<head><title>iMouse Alert Test</title></head>
<body style="font-family: Arial; max-width: 900px; margin: 24px;">
  <h2>iMouse Alert Test Panel</h2>
  <p>Send one message to Telegram, Slack, WhatsApp (any combo).</p>

  <form method="POST" action="/send">
    <div style="margin: 10px 0;">
      <label><input type="checkbox" name="ch" value="telegram" checked> Telegram</label>
      <label style="margin-left: 12px;"><input type="checkbox" name="ch" value="slack" checked> Slack</label>
      <label style="margin-left: 12px;"><input type="checkbox" name="ch" value="whatsapp" checked> WhatsApp</label>
    </div>

    <div style="margin: 10px 0;">
      <textarea name="msg" rows="6" style="width: 100%;" placeholder="Type message here..."></textarea>
    </div>

    <button type="submit" style="padding: 10px 16px;">Send Test</button>
  </form>

  <hr/>
  <h3>Config quick view (masked)</h3>
  <pre>{config}</pre>

  <hr/>
  <h3>Last Result</h3>
  <pre>{result}</pre>
</body>
</html>
"""

LAST_RESULT = "No test yet."

def masked(v: str) -> str:
    if not v:
        return ""
    if len(v) <= 6:
        return "***"
    return v[:3] + "***" + v[-3:]

def config_view() -> str:
    return json.dumps({
        "TELEGRAM_TOKEN": masked(get_env("TELEGRAM_TOKEN")),
        "TELEGRAM_CHAT_ID": get_env("TELEGRAM_CHAT_ID"),
        "SLACK_WEBHOOK_URL": masked(get_env("SLACK_WEBHOOK_URL")),
        "WHATSAPP_ENABLED": get_env("WHATSAPP_ENABLED"),
        "TWILIO_ACCOUNT_SID": masked(get_env("TWILIO_ACCOUNT_SID")),
        "WHATSAPP_FROM": get_env("WHATSAPP_FROM"),
        "WHATSAPP_TO": get_env("WHATSAPP_TO"),
    }, indent=2)

class Handler(BaseHTTPRequestHandler):
    def _send_html(self, html: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        global LAST_RESULT
        page = HTML.format(config=config_view(), result=LAST_RESULT)
        self._send_html(page)

    def do_POST(self):
        global LAST_RESULT
        if self.path != "/send":
            self._send_html("Not found", 404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8", "ignore")
        form = urllib.parse.parse_qs(data)

        channels = form.get("ch", [])
        msg = (form.get("msg", [""])[0] or "").strip()
        if not msg:
            msg = "🐭 iMouse Test Alert\nManual UI test"

        results = {}
        if "telegram" in channels:
            results["telegram"] = send_telegram(msg)
        if "slack" in channels:
            results["slack"] = send_slack(msg)
        if "whatsapp" in channels:
            results["whatsapp"] = send_whatsapp(msg)

        LAST_RESULT = json.dumps({"message": msg, "channels": channels, "results": results}, indent=2)
        log(f"TEST -> {LAST_RESULT}")
        page = HTML.format(config=config_view(), result=LAST_RESULT)
        self._send_html(page)

def main():
    env_path = None
    port = 5055

    for i, a in enumerate(sys.argv):
        if a == "--env" and i + 1 < len(sys.argv):
            env_path = sys.argv[i + 1]
        if a == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    if env_path:
        load_env_file(env_path)
        log(f"Loaded env file: {env_path}")

    log(f"Starting UI on http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()

if __name__ == "__main__":
    main()
