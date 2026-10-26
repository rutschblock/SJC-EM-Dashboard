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

CORRIDOR_START_MP=49.0  # Requested US 550 corridor southern boundary
CORRIDOR_END_MP=92.0  # Requested US 550 corridor northern boundary

def corridor_overlap(p):
    try:
        a=float(p.get('primaryMP')); b=float(p.get('secondaryMP'))
        return min(a,b)<=CORRIDOR_END_MP and max(a,b)>=CORRIDOR_START_MP
    except (ValueError,TypeError): return False

def near(f):
    p=f.get('properties') or {}
    return corridor_overlap(p)

def condition(c):
    return {k:c.get(k) for k in ('conditionDescription','sourceType','additionalData','updateTime','confirmationTime','endTime')}

def segment(f):
    p=f['properties']
    return {k:p.get(k) for k in ('id','name','nameId','routeName','primaryMP','secondaryMP') } | {'currentConditions':[condition(c) for c in (p.get('currentConditions') or []) if isinstance(c,dict)]}

def road_snapshot(segments):
    result={}
    for seg in segments:
        sid=str(seg.get('id') or seg.get('nameId') or seg.get('name'))
        reports=sorted({(str(c.get('conditionDescription') or '').strip(),str(c.get('additionalData') or '').strip()) for c in seg.get('currentConditions',[]) if c.get('sourceType')=='OPERATOR'})
        result[sid]={'name':seg.get('name') or seg.get('nameId') or sid,'reports':reports}
    return result

def compare_road_reports(before,after):
    changes=[]
    for sid in sorted(set(before)|set(after)):
        if sid not in before: changes.append({'segment':after[sid]['name'],'type':'new_segment','detail':'Newly reported segment; current operator report: '+('; '.join(' — '.join(filter(None,x)) for x in after[sid]['reports']) or 'none')})
        elif sid not in after: changes.append({'segment':before[sid]['name'],'type':'missing_segment','detail':'Previously reported segment absent from current feed; road status unknown'})
        elif before[sid]['reports']!=after[sid]['reports']:
            old='; '.join(' — '.join(filter(None,x)) for x in before[sid]['reports']) or 'No operator report'
            new='; '.join(' — '.join(filter(None,x)) for x in after[sid]['reports']) or 'No operator report'
            changes.append({'segment':after[sid]['name'],'type':'report_changed','detail':'Operator report changed from '+old+' to '+new})
    return changes

try:
    key=os.environ.get('CDOT_API_KEY','').strip()
    if not key: raise RuntimeError('CDOT_API_KEY secret is not configured')
    # Fetch pages defensively. Never silently claim complete coverage if the API
    # ignores pagination or returns a repeated/capped first page.
    features=[]; seen=set(); pagination_complete=False; pagination_note=''
    for page in range(1,21):
        params={'apiKey':key,'pageSize':100,'pageIndex':page}
        url='https://data.cotrip.org/api/v1/roadConditions?'+urllib.parse.urlencode(params)
        req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'SJC-EM-Dashboard/1.0'})
        with urllib.request.urlopen(req,timeout=35) as r:
            if r.status!=200: raise RuntimeError('CDOT HTTP '+str(r.status))
            raw=json.load(r)
        if raw.get('type')!='FeatureCollection' or not isinstance(raw.get('features'),list): raise RuntimeError('Unexpected CDOT response format')
        batch=raw['features']
        print(f'CDOT diagnostic: page={page} records={len(batch)} collection_keys={sorted(raw.keys())}',flush=True)
        fingerprints=[str((f.get('properties') or {}).get('id') or '')+'|'+str((f.get('properties') or {}).get('name') or '') for f in batch]
        duplicates=[x for x in fingerprints if x in seen]
        if page>1 and duplicates:
            print(f'CDOT diagnostic: page={page} duplicate_count={len(duplicates)} examples={duplicates[:5]}',flush=True)
            pagination_note='CDOT pagination returned repeated records; completeness unverified'
            break
        seen.update(fingerprints);features.extend(batch)
        if len(batch)<100:
            pagination_complete=True
            break
    else:
        pagination_note='CDOT page limit reached; completeness unverified'
    route=[f for f in features if str((f.get('properties') or {}).get('routeName','')).strip().upper()=='US 550']
    selected=[segment(f) for f in route if near(f)]
    print('CDOT diagnostic: total_features=',len(features),'us550_features=',len(route),'mp49_92_segments=',len(selected),flush=True)
    for seg in selected:
        print('CDOT corridor:',seg.get('id'),seg.get('primaryMP'),seg.get('secondaryMP'),seg.get('name'),flush=True)
    selected.sort(key=lambda f:float(f.get('primaryMP') or 0))
    # Coverage is based on explicit CDOT segment labels, not an inferred road condition.
    places={'Red Mountain Pass':('red mountain','ouray-silverton','ouray to silverton'), 'Silverton':('silverton',), 'Molas Pass':('molas', 'silverton-durango', 'silverton to durango')}
    coverage={name:{'reported':any(any(term in (str(seg.get('name') or '')+' '+str(seg.get('nameId') or '')).lower() for term in terms) for seg in selected),'matchingSegments':[str(seg.get('nameId') or seg.get('name')) for seg in selected if any(term in (str(seg.get('name') or '')+' '+str(seg.get('nameId') or '')).lower() for term in terms)]} for name,terms in places.items()}
    potentially_truncated=not pagination_complete
    if not selected: raise RuntimeError('No matching US 550 segments; corridor filter or API response needs review')
    if not pagination_complete:
        raise RuntimeError(pagination_note or 'CDOT feed completeness cannot be verified')
    previous_ok=prior.get('status')=='ok' and isinstance(prior.get('segments'),list)
    changes=compare_road_reports(road_snapshot(prior['segments']),road_snapshot(selected)) if previous_ok else []
    result={'changeTracking':{'initialized':previous_ok,'checkedAt':now,'changes':changes,'previousSuccessAt':prior.get('lastSuccessAt') if previous_ok else None},'status':'ok','checkedAt':now,'lastSuccessAt':now,'totalFeatures':len(features),'routeFeatures':len(route),'potentiallyTruncated':potentially_truncated,'paginationNote':pagination_note,'coverage':coverage,'segments':selected,'note':'Approximate geographic filter; road conditions do not confirm road open/closed.'}
except Exception as exc:
    result={'changeTracking':dict(prior.get('changeTracking') or {},unavailable=True),'status':'error','checkedAt':now,'lastSuccessAt':prior.get('lastSuccessAt'),'segments':prior.get('segments',[]),'coverage':prior.get('coverage',{}),'potentiallyTruncated':prior.get('potentiallyTruncated',False),'paginationNote':prior.get('paginationNote',''),'error':str(exc)[:180],'note':'CDOT retrieval failed; any displayed segments are previously retrieved data, not current road status.'}
    print('CDOT retrieval failed:',str(exc)[:180],file=sys.stderr)
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('CDOT status:',result['status'],'segments:',len(result['segments']))

# Fail the retrieval step when the published snapshot is marked unavailable.
# The workflow's publish step uses always() to preserve the stale/error warning.
if result['status'] != 'ok':
    sys.exit(1)
