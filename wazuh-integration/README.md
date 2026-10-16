# Wazuh to n8n integration

A custom Wazuh integration that forwards alerts to an n8n webhook, with built-in throttling. It feeds the Wazuh alert triage workflow (`wazuh-alert-triage.json` in the repo root).

## Files

- `custom-n8n`: shell wrapper that Wazuh runs, it starts the script below with Wazuh's bundled Python
- `custom-n8n.py`: reads the alert JSON and POSTs it to the webhook, after applying the throttle rules

## Throttle rules

- The same agent and rule can forward at most one alert per 15 minutes (`DEDUP_SECONDS`)
- At most 10 alerts per hour are forwarded in total (`MAX_PER_HOUR`)
- Throttled alerts are not lost: they stay in Wazuh, they are just not sent to n8n

The throttle lives in the integration and not in n8n on purpose. n8n stores workflow state only when an execution finishes, and each triage run takes up to 40 seconds (LLM retries). A burst of alerts starts all runs at once, before any of them saves state, so a throttle inside n8n would let the whole burst through. The script serializes the check with a file lock instead.

## Install

1. Copy both files to `/var/ossec/integrations/` on the Wazuh manager
2. Set permissions:
```
   sudo chmod 750 /var/ossec/integrations/custom-n8n /var/ossec/integrations/custom-n8n.py
   sudo chown root:wazuh /var/ossec/integrations/custom-n8n /var/ossec/integrations/custom-n8n.py
```
3. Create the throttle state file:
```
   sudo touch /var/ossec/logs/n8n-throttle.json
   sudo chown wazuh:wazuh /var/ossec/logs/n8n-throttle.json
   sudo chmod 660 /var/ossec/logs/n8n-throttle.json
```
4. Add this block inside `<ossec_config>` in `/var/ossec/etc/ossec.conf` (back the file up first):
```
   <integration>
     <name>custom-n8n</name>
     <hook_url>http://localhost:5678/webhook/wazuh-alert</hook_url>
     <level>8</level>
     <alert_format>json</alert_format>
   </integration>
```
5. Validate and restart:
```
   sudo /var/ossec/bin/wazuh-analysisd -t
   sudo systemctl restart wazuh-manager
```

## Notes

- Level 8 is deliberate. At level 5, a single Windows host produced over 2,000 alerts in one day, almost all of them audit failures and registry integrity events.
- Tested on Wazuh 4.14.8 on Ubuntu 26.04, which is not on the official supported list for 4.14 (installed with the `-i` flag). Treat that as a lab setup.
- The throttle was tested by running the script three times with the same alert against a local listener: exactly one request arrived.
