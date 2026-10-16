#!/usr/bin/env python3
import fcntl
import json
import sys
import time
import urllib.request

DEDUP_SECONDS = 900   # same agent + rule: at most one alert per 15 minutes
MAX_PER_HOUR = 10     # total alerts forwarded per hour
STATE_FILE = "/var/ossec/logs/n8n-throttle.json"

# Wazuh passes: argv[1] = alert file, argv[2] = api key (unused), argv[3] = hook_url
alert_file = sys.argv[1]
hook_url = sys.argv[3]

with open(alert_file) as f:
    alert = json.load(f)

key = "%s|%s" % (alert.get("agent", {}).get("name", ""), alert.get("rule", {}).get("id", ""))
now = time.time()

with open(STATE_FILE, "a+") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    lock.seek(0)
    try:
        state = json.loads(lock.read() or "{}")
    except ValueError:
        state = {}
    seen = {k: t for k, t in state.get("seen", {}).items() if now - t < DEDUP_SECONDS}
    sent = [t for t in state.get("sent", []) if now - t < 3600]

    if key in seen or len(sent) >= MAX_PER_HOUR:
        sys.exit(0)  # throttled: the alert stays in Wazuh, it is just not forwarded

    req = urllib.request.Request(
        hook_url,
        data=json.dumps(alert).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()

    seen[key] = now
    sent.append(now)
    lock.seek(0)
    lock.truncate()
    lock.write(json.dumps({"seen": seen, "sent": sent}))
