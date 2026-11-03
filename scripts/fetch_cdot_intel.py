#!/usr/bin/env python3
"""Fetch public CDOT ArcGIS alerts and weather-station data for SJC transportation.
A failed request preserves the last successful data but marks the source stale.
Missing events never imply that US 550 is open.
"""
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

OUT = pathlib.Path("data/cdot_intel.json")
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
old = {}
if OUT.exists():
    try: old=json.loads(OUT.read_text())
    except (OSError, ValueError): pass

BASE = "https://maps.codot.gov/server/rest/services/Hosted/"
LAYERS = {
 "alerts": "CoTrip_Alerts_Polyline_%28Live%29_Public_View/FeatureServer/0/query",
 "weather": "CoTrip_Weather_Stations_%28Live%29_Public_View/FeatureServer/0/query",
}
def download(name):
    params={
       "where":"1=1" if name=="alerts" else "ws_roadname LIKE '%550%'",
       "outFields":"*",
       "returnGeometry":"false",
       "f":"json",
       "resultRecordCount":"1000",
    }
    if name=="alerts":
        params.update({
          "geometry":json.dumps({"xmin":-108.13,"ymin":37.18,"xmax":-107.35,"ymax":38.14,"spatialReference":{"wkid":4326}},separators=(',',':')),
          "geometryType":"esriGeometryEnvelope",
          "inSR":"4326",
          "spatialRel":"esriSpatialRelIntersects",
        })
    url=BASE+LAYERS[name]+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"SJC-EM-Dashboard/1.0 (public safety)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=40) as response:
        body=json.load(response)
    if body.get("error"):raise RuntimeError(str(body["error"].get("message","ArcGIS error")))
    features=body.get("features")
    if not isinstance(features,list):raise RuntimeError("Missing feature list")
    return {"status":"ok","checkedAt":now,"features":[f.get("attributes",{}) for f in features],"truncated":bool(body.get("exceededTransferLimit")) or len(features)>=1000,"error":None}

result={}
for name in LAYERS:
    try:
        result[name]=download(name)
        print(name,"OK",len(result[name]["features"]),"features",flush=True)
    except Exception as exc:
        previous=old.get(name,{})
        result[name]={**previous,"status":"error","attemptedAt":now,"error":str(exc)[:220]}
        if "features" not in result[name]:result[name]["features"]=[]
        print(name,"ERROR",str(exc),flush=True)
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
