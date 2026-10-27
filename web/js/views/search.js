import { $, $$, api, CAT_LABEL, date, dur, esc, fail, h, icon, modal, num, on, pickFolder, shortPath, state, thumbUrl, toast } from '../core.js';
import { resultList } from '../resultlist.js';
import { lightbox } from '../lightbox.js';
import { searchView as legacySearch } from './search_legacy.js';
import { indexDialog } from '../discovery.js';
import { hasFeature } from '../features.js';

export function searchView(root, params) {
  if(params.get('preset')==='large')return legacySearch(root,params);
  let alive=true,timer,generation=0,items=[],offset=0;
  let text=params.get('q')||params.get('nl')||'',base={},sort=params.get('sort')||'ts',order=params.get('order')||'desc';
  let mode=params.get('mode')||(/\s/.test(text)&&!text.includes(':')?'photos':'files');
  if(!['files','photos','videos'].includes(mode))mode='files';
  if((mode==='photos'&&!hasFeature('photo_search'))||(mode==='videos'&&!hasFeature('video_search')))mode='files';
  try{base=JSON.parse(params.get('filters')||'{}');}catch{base={};}
  if(!base||typeof base!=='object'||Array.isArray(base))base={};
  for(const k of ['cat','ext'])if(params.get(k))base[k]=params.get(k).split(',');
  if(params.get('dir'))base.dir=params.get('dir');if(params.get('person'))base.person_id=+params.get('person');
  if(params.get('year')&&/^\d{4}$/.test(params.get('year'))){const year=+params.get('year');base.after=Date.UTC(year,0,1)/1000;base.before=Date.UTC(year+1,0,1)/1000;}
  const el=h(`<div class="view drive-search"><div class="page-head"><div class="grow"><div class="eyebrow">YOUR ENTIRE LIBRARY</div><h1>Find what you remember.</h1><p>Describe a moment. Find the photo, the scene, or the words.</p></div><button class="btn save-album">${icon('bookmark')}Save search</button></div>
    <div class="search-modes" role="group" aria-label="Search mode"><button data-mode="files">${icon('fileText')}Files & text</button><button data-mode="photos">${icon('images')}Photo meaning</button><button data-mode="videos">${icon('film')}Video scenes</button></div>
    <form class="drive-search-bar"><label class="sr-only" for="library-query">Search your library</label>${icon('search')}<input id="library-query" class="query" maxlength="500" autocomplete="off"><button type="button" class="clear-query btn icon ghost" aria-label="Clear search">${icon('x')}</button><button class="btn primary">Search</button></form>
    <div class="search-examples"></div><div class="drive-filters"><label class="file-type-control"><span class="sr-only">File type</span><select class="input type-filter"><option value="">Any type</option>${Object.entries(CAT_LABEL).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}<option value="pdf">PDF</option><option value="docx">Word documents</option></select></label><label><span class="sr-only">Library owner</span><select class="input owner-filter"><option value="">Any owner</option>${state.users.map(u=>`<option value="${esc(u.name)}">${esc(u.name)}</option>`).join('')}</select></label><button class="btn folder-filter">${icon('folder')}<span>Anywhere</span></button><button class="btn dates-filter">${icon('calendar')}Date</button><button class="btn ghost reset-filters">Reset filters</button><span class="grow"></span><label class="sort-control"><span class="sr-only">Sort results</span><select class="input sort-filter"><option value="ts:desc">Newest first</option><option value="ts:asc">Oldest first</option><option value="name:asc">Name A–Z</option><option value="size:desc">Largest first</option></select></label></div>
    <div class="search-feedback" role="status" aria-live="polite"></div><div class="search-person-matches"></div><div class="search-hint"><span class="mode-explanation"></span><button class="btn sm ghost index-settings">${icon('sparkles')}Search readiness</button></div><div class="semantic-results" hidden></div><div class="semantic-more"></div></div>`);
  root.append(el);$('.query',el).value=text;
  $('[data-mode="photos"]',el).hidden=!hasFeature('photo_search');$('[data-mode="videos"]',el).hidden=!hasFeature('video_search');$('.save-album',el).hidden=!hasFeature('albums');
  const list=resultList({filter:{ids:[-1]},sort,order,empty:'No matches. Try fewer words or remove a filter.'});el.append(list.el);
  function definition(){return {mode,q:$('.query',el).value.trim(),filter:base,sort,order};}
  function remember(){const p=new URLSearchParams({mode});if(text)p.set('q',text);if(Object.keys(base).length)p.set('filters',JSON.stringify(base));p.set('sort',sort);p.set('order',order);history.replaceState(null,'','#/search?'+p);}
  function controls(){
    const visual=mode!=='files';$$('.search-modes button',el).forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
    $('.index-settings',el).hidden=mode==='files'&&!hasFeature('documents')&&!hasFeature('ocr');
    list.el.hidden=visual;$('.semantic-results',el).hidden=!visual;$('.file-type-control',el).hidden=visual;$('.sort-control',el).hidden=visual;
    $('.type-filter',el).value=base.cat?.[0]||base.ext?.[0]||'';$('.owner-filter',el).value=base.owner||'';$('.sort-filter',el).value=sort+':'+order;
    $('.folder-filter span',el).textContent=base.dir?shortPath(base.dir):'Anywhere';$('.dates-filter',el).classList.toggle('selected',!!(base.after||base.before));
    $('.query',el).placeholder=visual?'Try “people drinking water”':'Names, document text, screenshots, or person:"Alex"';
    $('.mode-explanation',el).textContent=visual?'Closest visual matches, processed on your NAS. Results can be imperfect.':'Search names, document text and recognized text in images.';
    const examples=visual?['People drinking water','People riding bicycles','People running','A sunset at the beach']:['type:pdf invoice','person:"Alex" after:2024-01-01'];
    $('.search-examples',el).innerHTML=examples.map(q=>`<button class="query-example">${esc(q)}</button>`).join('');
    $$('.query-example',el).forEach(b=>b.onclick=()=>{$('.query',el).value=b.textContent;search();});
  }
  function drawImages(append=false){
    const host=$('.semantic-results',el);if(!append)host.innerHTML='<div class="meaning-grid"></div>';
    const grid=$('.meaning-grid',host),start=append?grid.children.length:0;
    grid.insertAdjacentHTML('beforeend',items.slice(start).map((it,i)=>`<button class="meaning-photo" data-photo="${i+start}" aria-label="Open ${esc(it.name)}${it.scene_id?' at '+dur(it.start_seconds):''}"><span class="meaning-thumb"><img loading="lazy" src="${it.scene_id?'/api/visual/frame/'+it.scene_id:thumbUrl(it,400)}" alt="">${it.scene_id?`<span class="scene-time">${icon('play')}${dur(it.start_seconds)}</span>`:''}</span><span class="meaning-caption"><strong>${esc(it.name)}</strong><small>${date(it.ts)}</small></span></button>`).join(''));
    $$('[data-photo]',host).forEach(b=>b.onclick=()=>lightbox([...items],+b.dataset.photo,{onDeleted:()=>search()}));
  }
  async function visual(append=false){
    const v=++generation,host=$('.semantic-results',el),description=$('.query',el).value.trim();
    if(!append){items=[];offset=0;host.innerHTML='<div class="empty"><div class="spin"></div><div>Looking through your library…</div></div>';}
    $('.semantic-more',el).innerHTML='';
    try{
      const s=await api('/visual/status?media='+(mode==='videos'?'video':'image'));if(!alive||v!==generation)return;
      $('.search-feedback',el).textContent=`${num(s.indexed)} of ${num(s.total)} ${mode==='videos'?'videos':'photos'} ready${s.task?' · indexing '+s.task.status:''}.`;
      if(!description){host.innerHTML=`<div class="meaning-empty">${icon('sparkles')}<h2>A few words can bring it back.</h2><p>Describe an activity, an object or a place. Try a suggestion above.</p>${!s.indexed?'<button class="btn primary prepare">Prepare visual search</button>':''}</div>`;$('.prepare',host)?.addEventListener('click',()=>indexDialog(mode).catch(fail));return;}
      if(!s.indexed){host.innerHTML=`<div class="meaning-empty">${icon('images')}<h2>Your library is getting ready.</h2><p>${s.task?'Indexing is '+s.task.status+'. Results appear as files are processed.':'Prepare your library once to search what photos and videos show.'}</p><button class="btn primary prepare">Search readiness</button></div>`;$('.prepare',host).onclick=()=>indexDialog(mode).catch(fail);return;}
      const filter={...base};delete filter.cat;delete filter.ext;
      const r=await api('/visual/search',{q:description,filter,media:mode==='videos'?'video':'image',offset,limit:60});if(!alive||v!==generation)return;
      items.push(...r.items);drawImages(append);
      $('.search-feedback',el).textContent=`${num(r.total)} closest ${r.total===1?'match':'matches'} · ${num(r.status.indexed)} ${mode==='videos'?'videos':'photos'} searchable${r.status.checked<r.status.total?' · library still being prepared':''}.`;
      if(!items.length)host.innerHTML='<div class="meaning-empty"><h2>No close matches yet.</h2><p>Try a simpler description, remove a filter, or index more of your library.</p></div>';
      if(r.has_more){$('.semantic-more',el).innerHTML='<button class="btn">Show more matches</button>';$('.semantic-more button',el).onclick=()=>{offset+=60;visual(true);};}
    }catch(error){if(alive&&v===generation){host.innerHTML=`<div class="empty">${esc(error.message)}</div>`;$('.search-feedback',el).textContent='Search could not finish.';}}
  }
  async function search(){
    clearTimeout(timer);text=$('.query',el).value.trim();remember();$('.search-person-matches',el).innerHTML='';if(mode!=='files')return visual();
    const v=++generation;$('.semantic-more',el).innerHTML='';$('.search-feedback',el).textContent='Searching…';
    try{const r=await api('/search/parse',{q:text});if(!alive||v!==generation)return;list.setFilter({...base,...r.filter},sort,order);
      $('.search-feedback',el).innerHTML=[...(base.person_id?[`<a class="chip on" href="#/people?id=${base.person_id}">Selected person</a>`]:[]),...r.labels.map(l=>`<span class="chip on">${esc(l.key)}: ${esc(l.value)}</span>`)].join('');
      if(!r.labels.length&&!base.person_id)$('.search-feedback',el).textContent=text?'Matching names and indexed text. Use Photo meaning to search the scene itself.':'All files in your selected libraries.';
      if(hasFeature('people')&&text&&!text.includes(':')){const people=await api('/people?q='+encodeURIComponent(text)+'&limit=6');if(alive&&v===generation)$('.search-person-matches',el).innerHTML=people.items.filter(p=>p.name).map(p=>`<a href="#/people?id=${p.id}" class="person-suggestion"><img src="/api/faces/${p.cover}/image" alt=""><span>${esc(p.name)}</span><small>${num(p.photos)} photos</small></a>`).join('');}
    }catch(error){if(alive&&v===generation)$('.search-feedback',el).textContent=error.message;}
  }
  $$('.search-modes button',el).forEach(b=>b.onclick=()=>{mode=b.dataset.mode;controls();search();});
  $('form',el).onsubmit=e=>{e.preventDefault();search();};$('.query',el).oninput=()=>{clearTimeout(timer);timer=setTimeout(search,mode==='files'?250:650);};
  $('.clear-query',el).onclick=()=>{$('.query',el).value='';$('.query',el).focus();search();};
  $('.type-filter',el).onchange=e=>{delete base.cat;delete base.ext;if(e.target.value)base[['pdf','docx'].includes(e.target.value)?'ext':'cat']=[e.target.value];search();};
  $('.owner-filter',el).onchange=e=>{if(e.target.value)base.owner=e.target.value;else delete base.owner;search();};
  $('.sort-filter',el).onchange=e=>{[sort,order]=e.target.value.split(':');search();};
  $('.folder-filter',el).onclick=async()=>{const dir=await pickFolder('Search in a folder',base.dir);if(dir!==null){if(dir)base.dir=dir;else delete base.dir;controls();search();}};
  $('.dates-filter',el).onclick=async()=>{const format=t=>t?new Date(t*1000).toISOString().slice(0,10):'';const body=h(`<div class="col"><label>From<input class="input after" type="date" value="${format(base.after)}"></label><label>Through<input class="input before" type="date" value="${format(base.before?base.before-86400:null)}"></label><p class="danger-text" role="alert"></p></div>`);const answer=await modal({title:'Choose dates',body,actions:[{label:'Cancel',value:null},{label:'Apply',value:'apply',cls:'primary',validate:()=>{if($('.after',body).value&&$('.before',body).value&&$('.after',body).value>$('.before',body).value){$('.danger-text',body).textContent='The end date must follow the start.';return false;}return true;}}]});if(answer==='apply'){delete base.after;delete base.before;if($('.after',body).value)base.after=Date.parse($('.after',body).value+'T00:00:00Z')/1000;if($('.before',body).value)base.before=Date.parse($('.before',body).value+'T00:00:00Z')/1000+86400;controls();search();}};
  $('.reset-filters',el).onclick=()=>{base={};controls();search();};$('.index-settings',el).onclick=()=>indexDialog(mode).then(()=>search()).catch(fail);
  $('.save-album',el).onclick=async()=>{const body=h('<div class="col"><label>Album name<input class="input album-name" maxlength="80" placeholder="Weekend rides"></label><p class="muted">Saves your search and filters. New matching files appear when indexed. Smart albums are shared in this SuperGallery account.</p></div>');const name=await modal({title:'Save a smart album',body,actions:[{label:'Cancel',value:null},{label:'Save album',cls:'primary',value:()=>$('.album-name',body).value.trim(),validate:()=>!!$('.album-name',body).value.trim()}]});if(name)try{await api('/albums',{name,definition:definition()});toast('Smart album saved.');}catch(e){fail(e);}};
  const offUsers=on('users-loaded',()=>{$('.owner-filter',el).innerHTML='<option value="">Any owner</option>'+state.users.map(u=>`<option value="${esc(u.name)}">${esc(u.name)}</option>`).join('');$('.owner-filter',el).value=base.owner||'';});
  const off=on('changed',e=>{if(['documents','faces','visual','scenes','ocr'].includes(e.detail?.kind))search();});
  controls();search();return()=>{alive=false;generation++;clearTimeout(timer);off();offUsers();list.destroy?.();};
}
