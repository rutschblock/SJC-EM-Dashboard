
/* Ambient Weather: read public-safe, server-generated snapshots only. */
(()=>{
  'use strict';
  const section=document.getElementById('ambient-stations-panel');
  if(!section)return;
  const state=document.getElementById('ambient-stations-status');
  const body=document.getElementById('ambient-stations-body');
  const refresh=document.getElementById('ambient-stations-refresh');
  const ageLabel=document.getElementById('ambient-stations-updated');
  const cell=(tr,value,klass='')=>{const td=document.createElement('td');td.textContent=value; if(klass)td.className=klass;tr.appendChild(td);return td;};
  const numeric=(value,digits=0,suffix='')=>Number.isFinite(Number(value))&&value!==null&&value!==''?Number(value).toFixed(digits)+suffix:'—';
  const age=(time)=>{const stamp=Date.parse(time||'');return Number.isFinite(stamp)?Date.now()-stamp:Infinity;};
  const localTime=(time)=>{const d=new Date(time);return Number.isFinite(d.getTime())?d.toLocaleString('en-US',{timeZone:'America/Denver',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}):'Unknown';};
  const chip=(tr,status)=>{const td=document.createElement('td');const s=document.createElement('span');s.className='ambient-chip '+(status==='Current'?'':status==='Stale'?'stale':'unavailable');s.textContent=status;td.appendChild(s);tr.appendChild(td);};
  async function load(){
    refresh.disabled=true;state.className='ambient-status';state.textContent='Checking Ambient Weather station observations…';
    try{
      const response=await fetch('./data/ambient_stations.json?ts='+Date.now(),{cache:'no-store'});
      if(!response.ok)throw Error('station feed not published');
      const data=await response.json();body.replaceChildren();
      const stations=Array.isArray(data.stations)?data.stations:[];
      ageLabel.textContent='Feed checked: '+localTime(data.checkedAt);
      for(const row of stations){
        const tr=document.createElement('tr');
        cell(tr,String(row.name||'Unnamed station'));
        cell(tr,numeric(row.tempF,1,' °F'),'num');
        cell(tr,numeric(row.humidityPct,0,'%'),'num');
        cell(tr,numeric(row.windMph,1,' mph'),'num');
        cell(tr,numeric(row.gustMph,1,' mph'),'num');
        cell(tr,numeric(row.rainHourIn,2,' in'),'num');
        cell(tr,numeric(row.rainDayIn,2,' in'),'num');
        cell(tr,localTime(row.observedAt));
        chip(tr,age(row.observedAt)<=30*60000?'Current':age(row.observedAt)<Infinity?'Stale':'Unavailable');
        body.appendChild(tr);
      }
      if(!stations.length){
        const tr=document.createElement('tr');
        cell(tr,data.status==='not_configured'?'Awaiting authorized local station connections.':'No authorized station observations available.').colSpan=9;
        body.appendChild(tr);
      }
      const staleCount=stations.filter(x=>age(x.observedAt)>30*60000).length;
      state.textContent=stations.length?stations.length+' authorized station(s) · '+staleCount+' stale or timestamp unavailable.':'Ambient Weather observations not yet configured.';
      if(data.status==='error'||data.status==='partial'||data.status==='not_configured')state.className='ambient-status warning';
    }catch(e){
      body.replaceChildren();ageLabel.textContent='Feed unavailable';
      state.className='ambient-status warning';state.textContent='Ambient Weather observations unavailable; no current readings verified.';
    }finally{refresh.disabled=false;}
  }
  refresh.addEventListener('click',load);
  load();
  setInterval(()=>{if(!document.hidden)load();},60*60*1000);
})();
