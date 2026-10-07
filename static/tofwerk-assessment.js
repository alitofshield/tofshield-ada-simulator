(() => {
  const root=document.querySelector('#tofwerk-workspace');
  let report=null;
  let opening=false;
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label={good:'Good for dev',conditional:'Conditional',not_suitable:'No good as supplied',unreviewed:'Not inspected'};
  const size=n=>`${(n/1e6).toFixed(1)} MB`;
  function render(){
    if(!report)return;
    root.querySelector('#review-progress').textContent=`${report.inspected} of ${report.total} files reviewed · ${(report.bytes/1e9).toFixed(2)} GB`;
    root.querySelector('#review-state').textContent=report.status;
    root.querySelector('#review-updated').textContent=`Updated ${new Date(report.updatedAt).toLocaleString()}`;
    const counts=Object.keys(label).map(s=>`<div class="review-stat ${s}"><strong>${report.rows.filter(r=>r.devStatus===s).length}</strong><span>${label[s]}</span></div>`).join('');
    root.querySelector('#review-counts').innerHTML=counts;
    const query=root.querySelector('#review-search').value.toLowerCase(), status=root.querySelector('#review-status').value, inst=root.querySelector('#review-instrument').value;
    const rows=report.rows.filter(r=>(!query||`${r.path} ${r.reasons.join(' ')}`.toLowerCase().includes(query))&&(!status||r.devStatus===status)&&(!inst||r.instrument===inst));
    root.querySelector('#review-results').textContent=`${rows.length} files shown`;
    root.querySelector('#review-tables').innerHTML=['Vocus CI-TOF','mipTOF','Other / unconfirmed'].map(group=>{
      const groupRows=rows.filter(r=>r.instrument===group);if(!groupRows.length)return '';
      return `<section class="review-group"><h2>${escape(group)} <span>${groupRows.length} files</span></h2><div class="review-table-scroll"><table><thead><tr><th>File</th><th>ADA development</th><th>ML training</th><th>Reason and required action</th></tr></thead><tbody>${groupRows.map(r=>`<tr><td class="review-file"><strong>${escape(r.name)}</strong><small>${escape(r.path)}</small><span>${size(r.sizeBytes)}${r.spectra!==null?' · '+Number(r.spectra).toLocaleString()+' stored spectra':''}</span>${typeof openReviewedFile==='function'?`<button type="button" class="button secondary review-open" data-review-path="${escape(r.path)}" aria-label="Open ${escape(r.name)} in viewer" ${opening?'disabled':''}>Open in viewer</button>`:''}</td><td><span class="review-badge ${escape(r.devStatus)}">${escape(r.devLabel)}</span></td><td><span class="review-ml">${escape(r.mlLabel)}</span></td><td><p>${escape(r.reasons[0])}</p><details><summary>Evidence &amp; next steps</summary><p class="review-evidence">${escape(r.evidence)}</p><p>${escape(r.instrumentBasis)}</p><ul>${r.reasons.slice(1).map(x=>`<li>${escape(x)}</li>`).join('')}</ul><strong>Required action</strong><ul>${r.actions.map(x=>`<li>${escape(x)}</li>`).join('')}</ul>${r.inspected?`<pre>${escape(JSON.stringify(r.coreChecks,null,2))}</pre><small>SHA-256: ${escape(r.sha256)}</small>`:''}${r.logNotes.length?`<details><summary>Acquisition log</summary><pre>${escape(JSON.stringify(r.logNotes,null,2))}</pre></details>`:''}</details></td></tr>`).join('')}</tbody></table></div></section>`;
    }).join('')||'<p class="review-empty">No files match these filters.</p>';
  }
  async function refresh(){try{const response=await fetch('/static/tofwerk-assessment.json',{cache:'no-store'});if(!response.ok)throw Error('Assessment file is unavailable');report=await response.json();render();root.querySelector('#review-error').textContent='';}catch(e){root.querySelector('#review-error').textContent=e.message;}}
  root.querySelector('#review-tables').addEventListener('click',async event=>{
    const button=event.target.closest('[data-review-path]');
    if(!button||opening)return;
    opening=true;
    root.querySelectorAll('[data-review-path]').forEach(b=>b.disabled=true);
    const errorBox=root.querySelector('#review-error');
    errorBox.textContent='';
    try { await openReviewedFile(button.dataset.reviewPath); }
    catch(error){errorBox.textContent=error.message;errorBox.scrollIntoView({block:'center'});}
    finally {opening=false;root.querySelectorAll('[data-review-path]').forEach(b=>b.disabled=false);}
  });
  ['review-search','review-status','review-instrument'].forEach(id=>root.querySelector('#'+id).addEventListener('input',render));
  root.querySelector('#review-refresh').addEventListener('click',refresh);
  root.querySelector('#review-export').addEventListener('click',()=>{
    if(!report)return;const quote=x=>'"'+String(x??'').replace(/"/g,'""')+'"';
    const rows=[['Instrument','File','ADA development','ML training','Evidence','Reasons','Required action','SHA-256'],...report.rows.map(r=>[r.instrument,r.path,r.devLabel,r.mlLabel,r.evidence,r.reasons.join(' '),r.actions.join(' '),r.sha256])];
    const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(r=>r.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='TOFWERK-HDF5-assessment.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  refresh();setInterval(()=>{if(root.classList.contains('active')&&!opening)refresh();},30000);
})();
