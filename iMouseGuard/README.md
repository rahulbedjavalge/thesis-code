# 🐭 iMouseGuard

**Real-time Behavioral Alerting System for Animal Surveillance**

A lightweight, event-driven monitoring and alerting platform for detecting and reporting animal behavior patterns from ZoneMinder video surveillance. Built with Python, WebSocket streaming, and multi-channel notifications.

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Components](#components)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Development](#development)
- [Documentation](#documentation)
- [Project Status](#project-status)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.6+
- ZoneMinder with Event Server (ZMES) running
- API credentials for notification channels (Telegram, Slack, Twilio)
- Access to ZoneMinder database (MariaDB)

### Local Development

```bash
# Clone and navigate
cd iMouseGuard

# Set up environment
cp env/prod.env .env
# Edit .env with your credentials

# Install dependencies
pip install -r requirements.txt

# Start the WebSocket forwarder
python bin/zmes_ws_to_telegram.py

# Or use manual trigger API for testing (separate terminal)
cd dev/manual_trigger_api
uvicorn app:app --host 127.0.0.1 --port 8000

# Open manual UI
open dev/manual_ui/index.html
```

### Docker (Production)

```bash
# Inside ZoneMinder container
docker exec zm_container bash -c "
  cd /opt/iMouseGuard/iMouseGuard
  python bin/zmes_ws_to_telegram.py
"
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│         ZoneMinder Video Surveillance                     │
│  (Cameras → Motion Detection → Events → Event Server)    │
└──────────────────────────────────────────────────────────┘
                         │
                         ↓ (WebSocket :9000)
          ┌──────────────────────────────┐
          │ zmes_ws_to_telegram.py       │
          │ (Forwarder + Deduplicator)   │
          │ • Persistent WebSocket conn  │
          │ • Event deduplication        │
          │ • Hook process spawner       │
          └──────────────────────────────┘
                         │
                         ↓ (stdin/stdout)
          ┌──────────────────────────────┐
          │ imouse_hook_alert.py         │
          │ (Enrichment + Delivery)      │
          │ • ZM API metadata fetch      │
          │ • Event enrichment           │
          │ • Rules evaluation           │
          │ • Message formatting         │
          └──────────────────────────────┘
                         │
          ┌──────────────┼──────────────┬──────────────┐
          ↓              ↓              ↓              ↓
    🔔 Telegram      💬 Slack       📲 WhatsApp    📞 Voice
    (with threads)  (with threading) (Twilio)     (Twilio)
```

---

## 🧩 Core Components

### bin/
**Main production scripts:**

| Script | Purpose |
|--------|---------|
| `zmes_ws_to_telegram.py` | WebSocket forwarder. Listens to ZoneMinder Event Server, deduplicates events, spawns alert hooks. |
| `imouse_hook_alert.py` | Alert enrichment & delivery engine. Fetches monitor/zone metadata, evaluates rules, sends notifications. |
| `rules_engine.py` | Rule evaluation system (currently under development). |
| `imouse_analyze.py` | Baseline analysis dashboard generator. |

### config/
**Configuration files:**
- `zmes_ws_only.ini` - ZoneMinder Event Server configuration (Perl)

### env/
**Environment variables:**
- `prod.env` - Production credentials and settings (⚠️ **Keep secret**)
- `prod.env.template` - Template for setup

### dev/
**Development tools:**

| Tool | Purpose |
|------|---------|
| `alert_test_server.py` | Standalone HTTP server for testing alert delivery without ZoneMinder |
| `manual_trigger_api/` | FastAPI REST endpoint for manually triggering alerts |
| `manual_ui/` | Browser-based UI for manual alert testing |

### analysis/
**Data analysis:**
- `analyze_tsv.py` - Convert raw TSV events to normalized CSV with visualizations
- `results/` - Analysis outputs (hourly trends, zone activity, score distributions)

### logs/, state/, tmp/
**Runtime files:**
- `logs/` - Process logs (zmes.log, ws_forwarder.log, hook.log)
- `state/` - Persistent state (seen events cache, etc.)
- `tmp/` - Temporary files

---

## ⚙️ Configuration

### Environment Variables

All credentials are managed via `env/prod.env`. Key variables:

```bash
# ZoneMinder
ZM_DB_NAME=zm
WS_URL=ws://127.0.0.1:9000
IMOUSE_API_BASE=http://127.0.0.1
IMOUSE_ZM_BASE_URL=http://10.0.2.2

# Telegram
TELEGRAM_TOKEN=<your-token>
TELEGRAM_CHAT_ID=<chat-id>
TELEGRAM_THREAD_ID=<optional-thread-id>

# Slack
SLACK_WEBHOOK_URL=<webhook-url>

# WhatsApp (Twilio)
WHATSAPP_ENABLED=1
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<token>
WHATSAPP_FROM=whatsapp:+14155238886
WHATSAPP_TO=whatsapp:+<target>

# Voice Calls
ENABLE_VOICE_CALL=1
VOICE_CALL_TO=+<target>
```

### Activity Windows (configuration.yml)

Define behavioral patterns by time:

```yaml
activity_windows:
  ACTIVE: "09:00-20:00"      # Peak activity hours
  SLEEP: "20:00-06:00"        # Rest period
  HYPER_ACTIVE: "17:00-22:00" # Hyperactivity threshold
```

---

## 📊 Behavioral Alerts

### Current Detectable Behaviors

- **LITTER_ABSENCE** - Mouse not in primary zone
- **DRINKING_INACTIVITY** - No activity at water station
- **HOUSE_MOVED** - Cage displacement detected
- **HYPERACTIVITY** - Excessive movement detected

### Behavior Rule Definitions (To Be Implemented)

The rules engine evaluates events against behavioral thresholds:

```python
# Example rule structure (rules_engine.py)
RULES = {
    'LITTER_ABSENCE': {
        'condition': 'zone_idle_seconds > 300',
        'severity': 'WARNING',
        'cooldown_sec': 600,
        'actions': ['telegram', 'slack']
    },
    'DRINKING_INACTIVITY': {
        'condition': 'food_zone_idle_seconds > 3600',
        'severity': 'INFO',
        'cooldown_sec': 3600
    },
    # ... more rules
}
```

---

## 🎯 Usage

### Production Deployment (Docker)

```bash
# Inside zm_container
docker exec zm_container bash /opt/iMouseGuard/iMouseGuard/bin/imouse_baseline.sh

# Monitor logs
docker exec zm_container tail -f /opt/iMouseGuard/iMouseGuard/logs/ws_forwarder.log
```

### Local Testing

**Option 1: Manual API Trigger**

```bash
# Start API server
cd dev/manual_trigger_api
uvicorn app:app --host 127.0.0.1 --port 8000

# Open http://localhost:8000 in browser and use the manual UI
```

**Option 2: Direct Hook Test**

```bash
# Test alert delivery
python bin/imouse_hook_alert.py 12345 1 <<< '{
  "behavior": "LITTER_ABSENCE",
  "severity": "WARNING",
  "monitor_id": 1,
  "zone_id": 5
}'
```

### Data Analysis

```bash
# Convert event data to normalized format
python analysis/analyze_tsv.py path/to/events.tsv

# Generates:
# - events_normalized.csv
# - hourly_normalized.csv
# - zones_summary_normalized.csv
# - visualizations
```

---

## 🛠️ Development

### Project Structure

```
iMouseGuard/
├── bin/                      # Production scripts
│   ├── zmes_ws_to_telegram.py
│   ├── imouse_hook_alert.py
│   ├── rules_engine.py
│   └── imouse_analyze.py
├── config/                   # Configuration files
├── env/                      # Environment & credentials
├── dev/                      # Development utilities
│   ├── alert_test_server.py
│   ├── manual_trigger_api/
│   └── manual_ui/
├── analysis/                 # Data analysis tools
├── docs/                     # Documentation
│   ├── OPERATIONS.md
│   ├── DEVELOPMENT.md
│   ├── RULES.md
│   └── experiments/
├── logs/                     # Runtime logs
├── state/                    # Persistent state
└── README.md                 # This file
```

### Running Tests

```bash
# Manual functional tests
python -m pytest tests/ -v

# Test alert delivery to all channels
python dev/alert_test_server.py

# Test with manual trigger API
# (See Quick Start → Local Development)
```

### Code Standards

- Python 3.6+
- Type hints where applicable
- Logging for all major operations
- Environment-based configuration (no hardcoded secrets)
- JSON for event payloads

---

## 📚 Documentation

Complete documentation is located in `docs/`:

| Document | Purpose |
|----------|---------|
| [OPERATIONS.md](docs/OPERATIONS.md) | Deployment, startup, monitoring, troubleshooting |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Development setup, testing procedures, debugging |
| [RULES.md](docs/RULES.md) | Behavioral rule definitions and thresholds |
| [API.md](docs/API.md) | Event payload schemas and API documentation |

### Experiment Data

Analysis results and experiment data stored in `docs/experiments/`:
- `monitor18_experiment_analysis.xlsx` - Baseline behavioral data
- `analysis_results/` - Processed analysis outputs

---

## 📈 Project Status

### ✅ Complete
- [x] WebSocket event streaming (zmes_ws_to_telegram.py)
- [x] Event enrichment pipeline (imouse_hook_alert.py)
- [x] Multi-channel notifications (Telegram, Slack, WhatsApp, Voice)
- [x] Manual testing tools (API, UI)
- [x] Data analysis framework
- [x] Docker deployment support

### 🔄 In Progress
- [ ] Rules engine implementation (behavioral thresholds)
- [ ] Advanced pattern matching
- [ ] Complex event correlation
- [ ] Performance optimization

### 📋 Planned
- [ ] Admin web dashboard
- [ ] Alert history database
- [ ] Machine learning-based anomaly detection
- [ ] Multi-facility deployment support

---

## 🐛 Troubleshooting

### WebSocket Connection Failed

```bash
# Check if Event Server is listening
ss -ltnp | grep ":9000"

# Check ZMES logs
tail -f /opt/iMouseGuard/iMouseGuard/logs/zmes.log
```

### Alerts Not Sending

```bash
# Verify credentials in prod.env
cat env/prod.env | grep -E "TELEGRAM|SLACK|TWILIO"

# Test direct hook execution
python bin/imouse_hook_alert.py 0 0 < test_payload.json
```

### High CPU/Memory Usage

- Check for zombie processes: `ps aux | grep python`
- Verify WebSocket ping/timeout settings in `env/prod.env`
- Monitor event deduplication: Check `state/` folder

---

## 📄 License & Attribution

**Thesis Project:** iMouseGuard - Real-time Animal Behavior Monitoring  
**Supervisor:** [Supervisor Name]  
**Institution:** [University Name]  
**Date Prepared:** March 23, 2026

### Dependencies
- **zmeventnotification** - Event Server (included in `zmeventnotification/`)
- **WebSocket client** - Real-time event streaming
- **Telegram Bot API** - Notifications
- **Slack API** - Notifications
- **Twilio** - WhatsApp & Voice

---

## 💬 Support

For issues or questions:
1. Check [DEVELOPMENT.md](docs/DEVELOPMENT.md) for troubleshooting
2. Review logs in `logs/` directory
3. Test manually using `dev/manual_trigger_api/` tool

**Last Updated:** March 23, 2026
