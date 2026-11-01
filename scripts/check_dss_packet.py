#!/usr/bin/env python3
"""Check the official NWS Grand Junction DSS PDF and write dashboard freshness metadata."""
import argparse
import datetime as dt
import hashlib
import io
import json
import pathlib
import re
import urllib.request
from pypdf import PdfReader

URL = "https://www.weather.gov/media/gjt/DssPacket.pdf"
OUT = pathlib.Path("data/dss_packet.json")
parser = argparse.ArgumentParser()
parser.add_argument("--event-check", action="store_true", help="Only fetch the DSS PDF if significant local weather alerts are active")
args = parser.parse_args()
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
previous = {}
if OUT.exists():
    try:
        previous = json.loads(OUT.read_text())
    except (ValueError, OSError):
        pass
result = dict(previous)
# Low-volume alert polling during potential events; only an active alert triggers an extra PDF fetch.
if args.event_check:
    try:
        headers = {"User-Agent": "SJC-EM-Dashboard (emergency management DSS monitoring)", "Accept": "application/geo+json"}
        # Include county and adjacent mountain / fire-weather forecast zones monitored by the dashboard.
        significant = ("winter storm", "blizzard", "snow squall", "winter weather", "ice storm",
                       "flood", "high wind", "wind advisory", "thunderstorm", "tornado",
                       "red flag", "fire weather", "extreme cold", "extreme heat")
        active = []
        for zone in ("COC111", "COZ018", "COZ019", "COZ295"):
            request = urllib.request.Request("https://api.weather.gov/alerts/active?zone=" + zone, headers=headers)
            with urllib.request.urlopen(request, timeout=18) as response:
                alerts = json.load(response).get("features", [])
            active.extend(x.get("properties", {}).get("event", "") for x in alerts)
        matches = sorted(set(event for event in active if any(word in event.lower() for word in significant)))
        if not matches:
            print("No significant active NWS alerts; skipping extra DSS PDF request")
            raise SystemExit(0)
        print("Event-based DSS check triggered by:", ", ".join(matches))
        result["check_mode"] = "event"
        result["trigger_alerts"] = matches
    except SystemExit:
        raise
    except Exception as exc:
        print("NWS alert status not verified; skipping event-only PDF request:", exc)
        raise SystemExit(0)
else:
    result["check_mode"] = "daily"
    result["trigger_alerts"] = []
result["checked_at"] = now
try:
    request = urllib.request.Request(URL, headers={"User-Agent": "SJC-EM-Dashboard/1.0 (official public NWS DSS PDF checker)", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=35) as response:
        pdf = response.read()
        modified = response.headers.get("Last-Modified")
    if not pdf.startswith(b"%PDF"):
        raise ValueError("Response was not a PDF")
    digest = hashlib.sha256(pdf).hexdigest()
    first_page = PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or ""
    # Prefer the packet's own 'Updated:' briefing date, not PDF file modification.
    match = re.search(r"Updated:\s*([^\n]+?)(?=National Weather Service|$|\n)", first_page, re.I)
    issued = match.group(1).strip() if match else None
    if digest != previous.get("sha256"):
        result["changed_at"] = now
    result.update({"url": URL, "sha256": digest, "packet_updated": issued, "http_last_modified": modified, "status": "ok", "error": None})
except Exception as exc:
    result.update({"status": "error", "error": str(exc)[:180]})
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(result["status"], result.get("packet_updated"), result["checked_at"])
