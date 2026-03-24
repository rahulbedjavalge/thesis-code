from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import time
import json, subprocess, sys, os
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


app = FastAPI(title="iMouseGuard Manual Trigger API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


ROOT_DIR = Path(__file__).resolve().parents[2]
HOOK_PATH = Path(os.environ.get("IMOUSE_HOOK_PATH", str(ROOT_DIR / "bin" / "imouse_hook_alert.py")))

# Priority order:
# 1) IMOUSE_ENV_FILE (explicit override)
# 2) local repo env/prod.env
# 3) server path /opt/iMouseGuard/iMouseGuard/.env
ENV_CANDIDATES = [
    os.environ.get("IMOUSE_ENV_FILE", ""),
    str(ROOT_DIR / "env" / "prod.env"),
    "/opt/iMouseGuard/iMouseGuard/.env",
]

# Load environment variables from prod.env
def load_env_file(path: str) -> dict:
    env = os.environ.copy()
    if not path or not os.path.exists(path):
        print(f"[WARN] ENV file not found: {path}")
        return env
    print(f"[INFO] Loading ENV from: {path}")
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
            v = v.strip()
            if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                v = v[1:-1]
            env[k] = v
            if k in ["TELEGRAM_TOKEN", "SLACK_WEBHOOK_URL", "TELEGRAM_CHAT_ID"]:
                print(f"[INFO] Loaded {k}: {v[:20]}...")
    print(f"[INFO] Total env vars: {len(env)}")
    return env


def load_env_from_candidates() -> tuple[dict, str]:
    for candidate in ENV_CANDIDATES:
        if candidate and os.path.exists(candidate):
            return load_env_file(candidate), candidate
    print("[WARN] No env file found in candidates, using current process env")
    return os.environ.copy(), "<process-env-only>"


SUBPROCESS_ENV, ACTIVE_ENV_FILE = load_env_from_candidates()

class TriggerPayload(BaseModel):
    behavior: str
    severity: str = "INFO"
    event_id: Optional[int] = None
    monitor_id: Optional[int] = None
    notes: Optional[str] = None
    zone_id: Optional[int] = None
    score: Optional[int] = None
    meta: Dict[str, Any] = {}

@app.get("/health")
def health():
    return {
        "ok": True,
        "ts": int(time.time()),
        "hook_path": str(HOOK_PATH),
        "env_file": ACTIVE_ENV_FILE,
    }


@app.get("/")
def index():
    ui_file = ROOT_DIR / "dev" / "manual_ui" / "index.html"
    if ui_file.exists():
        return FileResponse(ui_file)
    raise HTTPException(status_code=404, detail="manual_ui/index.html not found")

@app.post("/trigger")
def trigger(payload: TriggerPayload):
    if not HOOK_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Hook script not found: {HOOK_PATH}")

    data = payload.model_dump()

    eid = str(payload.event_id or 0)
    mid = str(payload.monitor_id or 0)

    p = subprocess.Popen(
        [sys.executable, str(HOOK_PATH), eid, mid],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=SUBPROCESS_ENV,
    )
    out, err = p.communicate(input=json.dumps(data))

    return {
        "received": True,
        "exit_code": p.returncode,
        "stdout": out[-2000:],
        "stderr": err[-2000:],
        "env_file": ACTIVE_ENV_FILE,
    }

