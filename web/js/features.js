import { $, $$, api, emit, esc, fail, h, icon, on, poll, state, toast } from './core.js';

export const ROUTE_FEATURES = {people:'people', albums:'albums', uploads:'uploads', quickclean:'cleanup', duplicates:'cleanup', similar:'cleanup', dupfolders:'cleanup', cleanup:'cleanup', rules:'automation'};
export function hasFeature(key) {
  return state.features?.[key] !== false && (key !== 'automation' || state.features?.cleanup !== false);
}
export function routeEnabled(key) { return !ROUTE_FEATURES[key] || hasFeature(ROUTE_FEATURES[key]); }
export function filteredNav(nav) { return nav.map(([label, items]) => [label, items.filter(([key]) => routeEnabled(key))]).filter(([,items]) => items.length); }
export function applyFeatureVisibility(root=document) {
  $$('a[href^="#/"]',root).forEach(a => { if(ROUTE_FEATURES[a.getAttribute('href').slice(2).split(/[/?]/)[0]]) a.hidden = !routeEnabled(a.getAttribute('href').slice(2).split(/[/?]/)[0]); });
}

export function featureCard(host) {
  let alive=true, busy=false, catalog=[];
  const el=h(`<section class="card feature-card"><h3>${icon('settings')}Features</h3><p class="muted">Choose the tools you use. Changes apply to everyone using this SuperGallery login.</p><div class="feature-options" aria-live="polite">Loading features…</div><p class="feature-note">Turning a feature off hides its tools, blocks its API and pauses related indexing. Saved indexes, names, albums and original files stay in place. Turn it back on, then resume indexing in Library intelligence or People. These switches are preferences, not account permissions.</p><p class="muted">File browsing, photos, security and backups stay available. Disabling cleanup does not prevent ordinary file deletion or change recycle-bin retention.</p><div class="release-info"></div></section>`);
  host.append(el);
  function draw(){
    if(!alive)return;
    $('.feature-options',el).innerHTML=catalog.map(f=>`<label class="feature-row"><span><strong>${esc(f.label)}</strong><small>${esc(f.description)}${f.key==='automation'&&!hasFeature('cleanup')?' Cleanup tools are currently off.':''}</small></span><input type="checkbox" role="switch" data-feature="${f.key}" aria-label="${esc(f.label)}" ${state.features[f.key]?'checked':''} ${busy?'disabled':''}></label>`).join('');
    $$('[data-feature]',el).forEach(input=>input.onchange=async()=>{
      const key=input.dataset.feature, value=input.checked;busy=true;$$('input',el).forEach(i=>i.disabled=true);
      try{const result=await api('/features',{values:{[key]:value}},'PUT');state.features=result.values;emit('features',result.values);toast(`${catalog.find(f=>f.key===key).label} ${value?'enabled':'disabled'}.`);poll(true);}
      catch(error){fail(error);}finally{busy=false;draw();$(`[data-feature="${key}"]`,el)?.focus();}
    });
  }
  api('/features').then(result=>{if(!alive)return;catalog=result.catalog;state.features=result.values;$('.release-info',el).innerHTML=`<span>SuperGallery ${esc(result.version)}</span><a href="https://github.com/SaiKrishnaDaddala/SuperGallery/releases" target="_blank" rel="noopener noreferrer">Releases and updates ${icon('right')}</a>`;draw();}).catch(fail);
  const off=on('features',()=>{if(!busy)draw();});return()=>{alive=false;off();};
}
