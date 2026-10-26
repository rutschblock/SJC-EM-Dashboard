import json, os, urllib.request, urllib.parse, datetime, pathlib, sys
OUT=pathlib.Path('data/cdot_us550.json')
OUT.parent.mkdir(exist_ok=True)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
prior={}
if OUT.exists():
    try: prior=json.loads(OUT.read_text())
    except (ValueError,OSError): pass

def in_bounds(lon,lat):
    try: return -108.10 <= float(lon) <= -107.55 and 37.24 <= float(lat) <= 38.08
    except (TypeError,ValueError): return False

def points(x):
    if isinstance(x,list):
        if len(x)>=2 and all(isinstance(v,(int,float)) for v in x[:2]): yield x[:2]
        else:
            for item in x: yield from points(item)

def near(f):
    p=f.get('properties') or {}
    if in_bounds(p.get('primaryLongitude'),p.get('primaryLatitude')) or in_bounds(p.get('secondaryLongitude'),p.get('secondaryLatitude')): return True
    return any(in_bounds(*xy) for xy in points((f.get('geometry') or {}).get('coordinates',[])))

def condition(c):
    return {k:c.get(k) for k in ('conditionDescription','sourceType','additionalData','updateTime','confirmationTime','endTime')}

def segment(f):
    p=f['properties']
    return {k:p.get(k) for k in ('id','name','nameId','routeName','primaryMP','secondaryMP') } | {'currentConditions':[condition(c) for c in (p.get('currentConditions') or []) if isinstance(c,dict)]}

try:
    key=os.environ.get('CDOT_API_KEY','').strip()
    if not key: raise RuntimeError('CDOT_API_KEY secret is not configured')
    url='https://data.cotrip.org/api/v1/roadConditions?'+urllib.parse.urlencode({'apiKey':key})
    req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'SJC-EM-Dashboard/1.0'})
    with urllib.request.urlopen(req,timeout=35) as r:
        if r.status!=200: raise RuntimeError('CDOT HTTP '+str(r.status))
        raw=json.load(r)
    if raw.get('type')!='FeatureCollection' or not isinstance(raw.get('features'),list): raise RuntimeError('Unexpected CDOT response format')
    features=raw['features']
    route=[f for f in features if str((f.get('properties') or {}).get('routeName','')).strip().upper()=='US 550']
    selected=[segment(f) for f in route if near(f)]
    selected.sort(key=lambda f:float(f.get('primaryMP') or 0))
    if not selected: raise RuntimeError('No matching US 550 segments; geographic filter may need adjustment')
    result={'status':'ok','checkedAt':now,'lastSuccessAt':now,'totalFeatures':len(features),'routeFeatures':len(route),'segments':selected,'note':'Approximate geographic filter; road conditions do not confirm road open/closed.'}
except Exception as exc:
    result={'status':'error','checkedAt':now,'lastSuccessAt':prior.get('lastSuccessAt'),'segments':prior.get('segments',[]),'error':str(exc)[:180],'note':'CDOT retrieval failed; any displayed segments are previously retrieved data, not current road status.'}
    print('CDOT retrieval failed:',str(exc)[:180],file=sys.stderr)
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('CDOT status:',result['status'],'segments:',len(result['segments']))
