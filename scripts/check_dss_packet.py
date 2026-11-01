#!/usr/bin/env python3
"""Check the official NWS Grand Junction DSS PDF and write dashboard freshness metadata."""
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
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
previous = {}
if OUT.exists():
    try:
        previous = json.loads(OUT.read_text())
    except (ValueError, OSError):
        pass
result = dict(previous)
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
    match = re.search(r"Updated:\\s*([^\\n]+?)(?=National Weather Service|$|\\n)", first_page, re.I)
    issued = match.group(1).strip() if match else None
    if digest != previous.get("sha256"):
        result["changed_at"] = now
    result.update({"url": URL, "sha256": digest, "packet_updated": issued, "http_last_modified": modified, "status": "ok", "error": None})
except Exception as exc:
    result.update({"status": "error", "error": str(exc)[:180]})
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(result["status"], result.get("packet_updated"), result["checked_at"])
