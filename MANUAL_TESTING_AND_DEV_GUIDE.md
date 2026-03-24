# Manual Testing and Development Guide - iMouseGuard

Date prepared: 2026-03-23

## A. Environment Setup

1. Open terminal in thesis/iMouseGuard.
2. Prepare virtual environment if needed.
3. Load environment variables from env/prod.env.
4. Confirm ZoneMinder API and event server connectivity.

## B. Start/Stop Basic Services

1. Start zmeventnotification event server with config/zmes_ws_only.ini.
2. Start WebSocket forwarder using bin/zmes_ws_to_telegram.py.
3. Verify process status and port 9000 listening.
4. Stop services and verify clean shutdown.

## C. Manual Functional Test Cases

### C1. Manual Hook Trigger Test

Objective:
Validate alert formatting and delivery end-to-end.

Steps:
1. Ensure environment variables are loaded.
2. Run bin/imouse_hook_alert.py with sample event id and monitor id.
3. Provide test JSON payload via stdin.
4. Verify message received in Telegram target chat/topic.

Expected:
- Event details are enriched.
- Message is delivered once.
- Link formatting is correct.

### C2. Forwarder Event Intake Test

Objective:
Validate WS event capture and handoff to hook.

Steps:
1. Start zmes_ws_to_telegram.py.
2. Trigger a ZoneMinder event.
3. Observe logs in logs/ws_forwarder.log.
4. Confirm hook execution and downstream alert.

Expected:
- Event detected.
- Duplicate handling behaves correctly.
- Hook invoked with valid payload.

### C3. Rules Engine Test

Objective:
Validate rule filtering/classification behavior.

Steps:
1. Adjust rules in bin/configuration.yml.
2. Replay or trigger representative events.
3. Validate decisions from rules_engine.py in logs/output.

Expected:
- Events are classified as configured.
- Rule priority/conflicts resolve correctly.

### C4. Manual Trigger API/UI Test

Objective:
Validate testing utilities for controlled submissions/demo.

Steps:
1. Start dev/manual_trigger_api/app.py.
2. Open dev/manual_ui/index.html.
3. Submit trigger request.
4. Verify API response and alert generation.

Expected:
- API accepts test payload.
- UI sends request successfully.
- End-to-end alert flow executes.

## D. Negative and Edge Tests

1. Invalid event id should fail safely with readable error.
2. Missing Telegram token should block delivery and log clear failure.
3. Down API endpoint should show retries/failure trace in logs.
4. Malformed payload should not crash service.

## E. Logs and Evidence Collection for Thesis

Collect and archive:

1. logs/zmes.log
2. logs/ws_forwarder.log
3. terminal screenshots for each test case
4. sample Telegram outputs/screenshots
5. analysis results under analysis/results/ and EXP/

## F. Development Workflow

1. Edit implementation in iMouseGuard/bin/.
2. Validate syntax and run local tests.
3. Use dev/manual_trigger_api and dev/manual_ui for repeatable demo.
4. Record behavior changes in notes or changelog.
5. Re-run manual functional test cases before packaging.

## G. Suggested Submission Checklist

1. Confirm all required files are present.
2. Confirm .env values are set for demo environment.
3. Confirm manual trigger test passes.
4. Confirm one real event test from ZoneMinder passes.
5. Include operation manual and this testing guide in final submission.
