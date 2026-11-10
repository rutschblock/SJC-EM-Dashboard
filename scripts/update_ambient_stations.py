
#!/usr/bin/env python3
"""Publish only explicitly authorized Ambient stations and safe observation fields.

Environment:
  AMBIENT_APPLICATION_KEY: app credential (GitHub Actions secret)
  AMBIENT_API_KEYS: one or more owner-granted API keys, comma-separated (secret)
  AMBIENT_STATION_NAMES: JSON object mapping allowed MAC addresses to PUBLIC labels
                         (GitHub Actions secret; no addresses or locations published)
"""
import datetime
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = pathlib.Path("data/ambient_stations.json")
FIELDS = {
    "tempF": "tempf",
    "humidityPct": "humidity",
    "windMph": "windspeedmph",
    "gustMph": "windgustmph",
    "rainHourIn": "hourlyrainin",
    "rainDayIn": "dailyrainin",
}
def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        v = float(value)
        return v if v == v and abs(v) != float("inf") else None
    except (ValueError, TypeError):
        return None

def to_iso(value):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.datetime.fromtimestamp(float(value) / 1000, datetime.timezone.utc).isoformat()
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(datetime.timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None

def main():
    checked = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = {"source": "Ambient Weather (authorized station owners)", "checkedAt": checked, "status": "not_configured", "stations": []}
    application_key = os.getenv("AMBIENT_APPLICATION_KEY", "").strip()
    keys = [v.strip() for v in os.getenv("AMBIENT_API_KEYS", "").split(",") if v.strip()]
    try:
        allowlist = json.loads(os.getenv("AMBIENT_STATION_NAMES", "{}"))
        if not isinstance(allowlist, dict): raise ValueError("station allowlist must be an object")
        allowlist = {str(k).strip().lower(): str(v)[:70] for k,v in allowlist.items() if str(v).strip()}
    except (ValueError, TypeError) as exc:
        raise SystemExit("AMBIENT_STATION_NAMES must be JSON mapping station MAC to public-safe display name") from exc

    if application_key and keys and allowlist:
        output["status"] = "ok"
        seen = set()
        errors = 0
        for index, api_key in enumerate(keys):
            if index: time.sleep(1.1)
            params = urllib.parse.urlencode({"applicationKey": application_key, "apiKey": api_key})
            url = "https://rt.ambientweather.net/v1/devices?" + params
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "SJC-EM-Dashboard/1.0"})
                with urllib.request.urlopen(req, timeout=20) as response:
                    payload = json.load(response)
                if not isinstance(payload, list):
                    raise ValueError("API device response not a list")
                for dev in payload:
                    mac = str(dev.get("macAddress", "")).lower()
                    if mac not in allowlist or mac in seen: continue
                    data = dev.get("lastData") or {}
                    # Only a named station plus meteorological readings is published.
                    station = {"name": allowlist[mac], "observedAt": to_iso(data.get("dateutc") or data.get("date"))}
                    for output_name, api_field in FIELDS.items():
                        station[output_name] = number(data.get(api_field))
                    output["stations"].append(station)
                    seen.add(mac)
            except (urllib.error.URLError, ValueError, TimeoutError) as exc:
                errors += 1
                # Never print URLs or query strings: both contain API secrets.
                print("Ambient Weather owner feed unavailable:", type(exc).__name__)
        if errors: output["status"] = "partial" if output["stations"] else "error"
        output["stations"].sort(key=lambda s:s["name"].lower())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print("Ambient Weather:", output["status"], len(output["stations"]), "stations")

if __name__ == "__main__":
    main()
