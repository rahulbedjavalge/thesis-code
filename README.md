# iMouseGuard

Real-time Behavioral Alerting System for Animal Surveillance

This repository contains iMouseGuard, a lightweight event-driven monitoring and alerting platform for detecting and reporting animal behavior patterns from ZoneMinder video surveillance.

## Overview

iMouseGuard receives events from ZoneMinder Event Server over WebSocket, enriches those events with ZoneMinder API metadata, evaluates behavior-oriented conditions, and sends notifications through configured channels.

## Architecture

### At a Glance

```text
ZoneMinder (API + ES:9000)
   | (WebSocket)
   v
 zmes_ws_to_telegram.py  --(stdin JSON)-->  imouse_hook_alert.py
   |                                       |
   +----------- guard scripts manage both -+
           |
           v
         Notification APIs
```

### Detailed Flow

```text
ZoneMinder cameras -> motion detection -> Event Server (ES:9000 WebSocket)
  |
  v
zmes_ws_to_telegram.py (forwarder)
- maintains WebSocket connection
- de-duplicates event IDs
- spawns a hook subprocess per event
  |
  | argv: eid, mid
  | stdin: {behavior, notes, monitor_name}
  v
imouse_hook_alert.py (hook)
- fetches event and monitor data from ZoneMinder API
- formats alert messages
- sends notifications to configured channels
```

Primary channels currently supported:
- Telegram (with optional topic/thread)
- Slack
- WhatsApp (Twilio)
- Voice calls (Twilio)

## Repository Layout

```text
thesis-code/
|-- README.md
|-- LICENSE
|-- iMouseGuard_Operations_Manual.md
|-- MANUAL_TESTING_AND_DEV_GUIDE.md
|-- EXP/
|-- iMouseGuard/
|   |-- bin/
|   |   |-- configuration.yml
|   |   |-- imouse_hook_alert.py
|   |   |-- rule.py
|   |   |-- rules_engine.py
|   |   `-- zmes_ws_to_telegram.py
|   |-- config/
|   |   `-- zmes_ws_only.ini
|   |-- dev/
|   |   |-- alert_test_server.py
|   |   |-- manual_trigger_api/
|   |   `-- manual_ui/
|   |-- docs/
|   |   |-- RULES.md
|   |   `-- experiments/
|   |-- env/
|   |   |-- prod.env
|   |   `-- prod.env.template
|   |-- logs/
|   |-- state/
|   `-- tmp/
`-- zmeventnotification/
```

## Core Components

- `iMouseGuard/bin/zmes_ws_to_telegram.py`
  Receives Event Server messages, de-duplicates events, and triggers hook processing.
- `iMouseGuard/bin/imouse_hook_alert.py`
  Enriches event context and sends notifications.
- `iMouseGuard/bin/rules_engine.py`
  Rule evaluation logic for behavior-based alerts.
- `iMouseGuard/bin/rule.py`
  Supporting rule definitions and rule utility logic.

## Quick Start

### Prerequisites

- Python 3.6+
- ZoneMinder with Event Server (ZMES) available
- API credentials for required notification channels
- Access to ZoneMinder database and API endpoints

### Local Setup

```bash
cd iMouseGuard
cp env/prod.env .env
pip install -r requirements.txt
python bin/zmes_ws_to_telegram.py
```

### Manual Trigger Testing

```bash
cd iMouseGuard/dev/manual_trigger_api
uvicorn app:app --host 127.0.0.1 --port 8000
```

## Configuration

Environment values are managed in `iMouseGuard/env/prod.env`.

Common variables include:

- `WS_URL`
- `IMOUSE_API_BASE`
- `IMOUSE_ZM_BASE_URL`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_THREAD_ID`
- `SLACK_WEBHOOK_URL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`

## Usage

### Run Forwarder

```bash
python iMouseGuard/bin/zmes_ws_to_telegram.py
```

### Run Direct Hook Test

```bash
python iMouseGuard/bin/imouse_hook_alert.py 12345 1
```

### Run Analysis

```bash
python iMouseGuard/analysis/analyze_tsv.py path/to/events.tsv
```

## Troubleshooting

### Event Server Connection Issues

- Confirm Event Server is listening on port 9000.
- Validate `WS_URL` and API base URLs in environment configuration.
- Inspect logs under `iMouseGuard/logs/`.

### Alert Delivery Issues

- Verify credentials and destination identifiers.
- Run a direct hook test to isolate notification channel issues.

## Security Notes

- Do not commit secrets or tokens.
- Restrict permissions for environment files, especially `prod.env`.
- Review all outbound notification endpoints before production deployment.

## License

This repository is proprietary and confidential.

No person or organization is permitted to use, copy, modify, distribute, publish, sublicense, or create derivative works from any part of this repository without prior written permission from the copyright holder.

See `LICENSE` for complete terms.
