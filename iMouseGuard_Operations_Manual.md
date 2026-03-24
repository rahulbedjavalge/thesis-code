# 🐭 iMouseGuard Operations Manual

**Environment:** Inside ZoneMinder Docker container\
**Components:**\
- ZMES (Perl WebSocket event server)\
- WS Forwarder (Python)\
- Hook (`imouse_hook_alert.py`)\
- ZoneMinder DB (MariaDB)

------------------------------------------------------------------------

# 📌 1. Quick Status Check

## Check if ZMES + Forwarder are running

``` bash
ps aux | egrep "zmeventnotification.pl|zmes_ws_to_telegram.py" | grep -v egrep
```

## Check if WebSocket port is listening

``` bash
ss -ltnp | grep ":9000" || echo "9000 not listening"
```

## Check recent logs

``` bash
tail -n 30 /opt/iMouseGuard/iMouseGuard/logs/zmes.log
tail -n 30 /opt/iMouseGuard/iMouseGuard/logs/ws_forwarder.log
```

------------------------------------------------------------------------

# 🚀 2. Start Services

## Start ZMES (Perl Event Server)

``` bash
mkdir -p /opt/iMouseGuard/iMouseGuard/logs
cd /opt/iMouseGuard/zmeventnotification

nohup perl -T zmeventnotification.pl   --config=/opt/iMouseGuard/iMouseGuard/config/zmes_ws_only.ini   > /opt/iMouseGuard/iMouseGuard/logs/zmes.log 2>&1 &

echo $! > /opt/iMouseGuard/iMouseGuard/logs/zmes.pid
```

Verify:

``` bash
ss -ltnp | grep ":9000"
```

------------------------------------------------------------------------

## Start WS Forwarder (Python)

``` bash
cd /opt/iMouseGuard/iMouseGuard

nohup bash -lc '
set -a
source .env
set +a
source venv/bin/activate
python bin/zmes_ws_to_telegram.py
' > logs/ws_forwarder.log 2>&1 &

echo $! > logs/ws_forwarder.pid
```

Verify:

``` bash
ps aux | egrep "zmes_ws_to_telegram.py" | grep -v egrep
```

------------------------------------------------------------------------

# 🛑 3. Stop Services

## Stop Forwarder

``` bash
pkill -f zmes_ws_to_telegram.py || true
```

## Stop ZMES

``` bash
pkill -f zmeventnotification.pl || true
```

Confirm stopped:

``` bash
ps aux | egrep "zmeventnotification.pl|zmes_ws_to_telegram.py" | grep -v egrep || echo "stopped"
```

------------------------------------------------------------------------

# 📂 4. Edit Configuration / Scripts

## Edit environment variables

``` bash
nano /opt/iMouseGuard/iMouseGuard/.env
```

## Edit ZMES config

``` bash
nano /opt/iMouseGuard/iMouseGuard/config/zmes_ws_only.ini
```

## Edit Hook Script

``` bash
nano /opt/iMouseGuard/iMouseGuard/bin/imouse_hook_alert.py
```

## Syntax check Python files

``` bash
python -m py_compile /opt/iMouseGuard/iMouseGuard/bin/imouse_hook_alert.py
```

------------------------------------------------------------------------

# 📜 5. Log Locations

  Component   Log File
  ----------- ------------------------------------------------------
  ZMES        `/opt/iMouseGuard/iMouseGuard/logs/zmes.log`
  Forwarder   `/opt/iMouseGuard/iMouseGuard/logs/ws_forwarder.log`

Live tail:

``` bash
tail -f logs/zmes.log
tail -f logs/ws_forwarder.log
```

------------------------------------------------------------------------

# 🧪 6. Manual Hook Test

``` bash
cd /opt/iMouseGuard/iMouseGuard
set -a; source .env; set +a
source venv/bin/activate

python bin/imouse_hook_alert.py 123456 18 <<<'{"behavior":"zm_event","notes":"Manual test"}'
```

------------------------------------------------------------------------

# 🧩 7. Get Zone Name for an Event (DB Debug)

``` bash
mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" zm -e "
SELECT s.EventId, s.ZoneId, z.Name, s.Score, s.AlarmPixels, s.Blobs
FROM Stats s
JOIN Zones z ON z.Id=s.ZoneId
WHERE s.EventId=988796
ORDER BY s.Score DESC
LIMIT 5;"
```

------------------------------------------------------------------------

# 🛠 8. Troubleshooting Checklist

## 9000 not listening

-   ZMES not running
-   Wrong directory when starting Perl
-   Config path incorrect

## Receiving events but no Telegram

-   Check `.env` variables
-   Verify `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`
-   Check hook logs

## WhatsApp 429 error

-   Twilio rate limit
-   Reduce frequency
-   Add cooldown

------------------------------------------------------------------------

**End of Document**


# TO EDIT ENV FILE
nano /opt/iMouseGuard/iMouseGuard/.env


# export IMOUSE_ALLOWED_MONITORS=18
# OR
# export IMOUSE_ALLOWED_MONITORS=
 