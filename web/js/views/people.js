import { $, $$, api, esc, fail, h, icon, modal as coreModal, num, on, poll, toast } from '../core.js';
import { lightbox } from '../lightbox.js';

const faceImage = id => `/api/faces/${id}/image`;
const displayName = p => p.name || 'Add a name';
const modal = (title, body, actions) => coreModal({title, body, actions});

export function peopleView(root, params) {
  let alive = true, version = 0, offset = 0, searchTimer, statusTimer, current, capability = false, selecting = false;
  const picked = new Map();
  const pid = Number(params.get('id')) || null;
  const el = h(`<div class="view people-view"><div class="page-head"><div class="grow"><div class="eyebrow">YOUR PHOTO LIBRARY</div><h1>People</h1><p>Familiar faces. All in one place.</p></div><button class="btn index-people">${icon('sparkles')}Find people</button></div>
    <div class="people-progress" aria-live="polite"></div><div class="people-toolbar"><div class="search-box">${icon('search')}<input class="find-person" aria-label="Find a person" placeholder="Find someone by name"></div><button class="btn select-people">${icon('selectAll')}Select</button><button class="btn ghost privacy">${icon('lock')}On your NAS</button></div><div class="people-content"><div class="empty"><div class="spin"></div></div></div><div class="people-selbar" hidden></div></div>`);
  root.append(el);

  async function refreshStatus() {
    try {
      const s = await api('/people/status'); if (!alive) return;
      capability = s.celebrity_available;
      const remaining = Math.max(0, s.total - s.checked - s.errors - s.unsupported);
      $('.people-progress', el).innerHTML = s.task ? `<div class="index-banner"><div class="grow"><b>${s.task.status === 'queued' ? 'Waiting to find people' : 'Finding familiar faces…'}</b><p>${esc(s.task.message || 'Your NAS will process your photos in the background.')}</p><progress value="${s.task.done}" max="${Math.max(1, s.task.total)}"></progress></div><button class="btn sm pause-index">Pause</button></div>` :
        `<div class="index-summary">${icon('lock')}<span>${num(s.checked)} of ${num(s.total)} photos checked on your NAS${remaining ? ` · ${num(remaining)} waiting` : ''}${s.errors ? ` · ${num(s.errors)} unreadable` : ''}${s.unsupported ? ` · ${num(s.unsupported)} unsupported` : ''}</span></div>`;
      $('.index-people', el).disabled = !!s.task;
      $('.index-people', el).innerHTML = `${icon('sparkles')}${s.checked ? 'Find new faces' : 'Find people'}`;
      $('.pause-index', el)?.addEventListener('click', async () => { try { await api(`/tasks/${s.task.id}/cancel`, {}); await refreshStatus(); } catch (e) { fail(e); } });
      clearTimeout(statusTimer); if (s.task) statusTimer = setTimeout(refreshStatus, 3000);
    } catch (e) { if (alive) fail(e); }
  }

  async function load(append = false) {
    const v = ++version;
    try {
      if (pid) {
        try { current = await api(`/people/${pid}?offset=${offset}`); }
        catch (e) { if (/not found/i.test(e.message)) { toast('That person has no photos left.', 'info'); location.hash = '#/people'; return; } throw e; }
        if (alive && v === version) drawPerson(current, append);
      }
      else {
        const q = $('.find-person', el).value.trim();
        const r = await api(`/people?q=${encodeURIComponent(q)}&offset=${offset}`);
        if (!alive || v !== version) return;
        const host = $('.people-content', el);
        if (!append) host.innerHTML = r.total ? '<div class="people-grid"></div>' : `<div class="people-empty"><div class="people-empty-icon">${icon('users')}</div><h2>${q ? 'No person with that name' : 'Make room for familiar faces'}</h2><p>${q ? 'Try another name, or clear the search to see unnamed groups.' : 'Find people groups faces from your photos here. Add names, bring matching groups together, and revisit every moment with someone.'}</p>${q ? '' : '<button class="btn primary start-faces">Find people in my photos</button>'}</div>`;
        $('.start-faces', host)?.addEventListener('click', start);
        $('.people-grid', host)?.insertAdjacentHTML('beforeend', r.items.map(p => `<a class="person-card ${p.name ? '' : 'unnamed'}${picked.has(p.id) ? ' picked' : ''}" href="#/people?id=${p.id}" data-id="${p.id}" data-owner="${esc(p.owner)}" data-name="${esc(p.name || '')}" data-photos="${p.photos}" data-cover="${p.cover}"><span class="pick-mark" aria-hidden="true">${icon('check')}</span><img loading="lazy" src="${faceImage(p.cover)}" alt="" width="160" height="160"><strong>${esc(displayName(p))}</strong><span>${num(p.photos)} ${p.photos === 1 ? 'photo' : 'photos'}</span></a>`).join(''));
        moreButton(host, offset + r.items.length < r.total);
        wireCards(host);
      }
    } catch (e) { if (alive) { $('.people-content', el).innerHTML = `<div class="empty"><h2>Couldn’t load people</h2><p>${esc(e.message)}</p><button class="btn retry">Try again</button></div>`; $('.retry', el).onclick = () => load(); } }
  }

  function moreButton(host, more) {
    $('.more-people', host)?.remove();
    if (!more) return;
    host.insertAdjacentHTML('beforeend', '<button class="btn more-people">Show more</button>');
    $('.more-people', host).onclick = async e => { e.target.disabled = true; offset += 120; await load(true); };
  }

  function drawPerson(person, append) {
    const host = $('.people-content', el);
    $('.people-toolbar', el).hidden = true;
    if (!person.total) {
      $('h1', el).textContent = person.name || 'Unnamed person';
      $('.page-head p', el).textContent = 'No photos right now.';
      host.innerHTML = `<a class="back-link" href="#/people">${icon('left')}All people</a><div class="people-empty"><div class="people-empty-icon">${icon('users')}</div><h2>No photos of this person are left</h2><p>They were deleted or moved to someone else. If that was a mistake, restore them from Recently deleted and they will appear here again.</p><div class="row" style="justify-content:center;gap:10px"><a class="btn" href="#/trash">Recently deleted</a><a class="btn primary" href="#/people">Back to People</a></div></div>`;
      return;
    }
    $('h1', el).textContent = person.name || 'Unnamed person';
    $('.page-head p', el).textContent = `${num(person.total)} faces · Matches are suggestions. You can correct them below.`;
    if (!append) host.innerHTML = `<a class="back-link" href="#/people">${icon('left')}All people</a><div class="person-actions"><button class="btn primary name-person">${icon('edit')}${person.name ? 'Edit name' : 'Add a name'}</button><a class="btn" href="#/search?person=${person.id}">${icon('images')}View all photos</a><button class="btn merge-person">Merge with…</button><button class="btn ghost celebrity-person">Celebrity suggestion</button></div><div class="face-grid"></div>`;
    $('.face-grid', host).insertAdjacentHTML('beforeend', person.faces.map(f => `<div class="face-card" data-face="${f.id}"><button class="face-open" aria-label="Open ${esc(f.filename)}" data-file="${f.file_id}"><img loading="lazy" src="${faceImage(f.id)}" alt="Face from ${esc(f.filename)}" width="240" height="240"></button><div class="face-caption"><span title="${esc(f.filename)}">${esc(f.filename)}</span><button class="btn sm ghost correct-face">Correct match</button></div></div>`).join(''));
    $('.name-person', host).onclick = () => namePerson(person);
    $('.merge-person', host).onclick = () => mergePerson(person);
    $('.celebrity-person', host).onclick = () => celebrity(person);
    $$('.face-open', host).forEach(b => b.onclick = async () => {
      try {
        const r = await api('/query', {filter: {person_id: person.id}, sort: 'ts', order: 'desc', limit: 1000});
        const items = r.items.length ? r.items : (await api('/query', {filter: {ids: [+b.dataset.file]}})).items;
        const start = Math.max(0, items.findIndex(it => it.id === +b.dataset.file));
        if (items.length) lightbox(items, start, {onDeleted: () => { offset = 0; load(); }});
      } catch (e) { fail(e); }
    });
    $$('.correct-face', host).forEach(b => b.onclick = () => correct(+b.closest('[data-face]').dataset.face));
    moreButton(host, offset + person.faces.length < person.total);
  }

  function wireCards(host) {
    $('.people-grid', host)?.classList.toggle('selecting', selecting);
    $$('.person-card', host).forEach(card => card.onclick = e => {
      if (!selecting) return;
      e.preventDefault();
      const id = +card.dataset.id;
      if (picked.has(id)) picked.delete(id);
      else picked.set(id, {id, owner: card.dataset.owner, name: card.dataset.name, photos: +card.dataset.photos, cover: +card.dataset.cover});
      card.classList.toggle('picked', picked.has(id));
      drawSelbar();
    });
  }

  function setSelecting(on) {
    selecting = on;
    if (!on) picked.clear();
    $('.select-people', el).innerHTML = on ? `${icon('x')}Cancel` : `${icon('selectAll')}Select`;
    $$('.person-card', el).forEach(card => card.classList.remove('picked'));
    $('.people-grid', el)?.classList.toggle('selecting', on);
    drawSelbar();
  }

  function drawSelbar() {
    const bar = $('.people-selbar', el), list = [...picked.values()];
    bar.hidden = !selecting;
    if (!selecting) return;
    const owners = new Set(list.map(p => p.owner));
    bar.innerHTML = `<span><b>${num(list.length)}</b> selected</span><span class="muted">${list.length < 2 ? 'Pick the groups that are the same person' : owners.size > 1 ? 'People from different libraries can’t be merged' : ''}</span><span class="grow"></span><button class="btn primary merge-picked" ${list.length < 2 || owners.size > 1 ? 'disabled' : ''}>Merge into one person</button>`;
    $('.merge-picked', bar).onclick = () => mergePicked(list);
  }

  async function mergePicked(list) {
    // Keep a named group if there is one, otherwise the largest.
    const keep = [...list].sort((a, b) => (!!b.name - !!a.name) || (b.photos - a.photos))[0];
    const body = h(`<div class="col"><p>All ${num(list.reduce((s, p) => s + p.photos, 0))} photos become one person. Choose which name and cover to keep.</p>
      <div class="target-results">${list.map(p => `<label class="person-option"><input type="radio" name="keep" value="${p.id}" ${p.id === keep.id ? 'checked' : ''}><img src="${faceImage(p.cover)}" alt=""><span>${esc(p.name || 'Unnamed person')} · ${num(p.photos)} ${p.photos === 1 ? 'photo' : 'photos'}</span></label>`).join('')}</div>
      <p class="muted">You can still correct individual photos afterwards.</p><p class="dialog-error danger-text" role="alert"></p></div>`);
    const ok = await modal(`Merge ${list.length} people?`, body, [{label: 'Cancel', value: null}, {label: 'Merge', value: 'merge', cls: 'primary', validate: async () => {
      const target = +$('input[name=keep]:checked', body).value;
      try {
        for (const p of list) if (p.id !== target) await api(`/people/${p.id}/merge`, {target});
        return true;
      } catch (e) { $('.dialog-error', body).textContent = e.message; return false; }
    }}]);
    if (ok !== 'merge') return;
    setSelecting(false);
    offset = 0; await load();
    toast(`Merged ${list.length} groups into one person.`);
  }

  async function namePerson(person, suggestion = '') {
    const body = h(`<div class="col"><label for="person-name">Name</label><input id="person-name" class="input" maxlength="80" autocomplete="off" placeholder="Who is this?"><p class="muted">This name will appear in People and search. It stays on your NAS.</p><p class="dialog-error danger-text" role="alert"></p></div>`);
    $('input', body).value = suggestion || person.name;
    await modal('Name this person', body, [{label:'Cancel'}, {label:'Save name', cls:'primary', value:'saved', validate:async()=>{try{await api(`/people/${person.id}/name`,{name:$('input',body).value});offset=0;load();return true;}catch(e){$('.dialog-error',body).textContent=e.message;return false;}}}]);
  }

  async function chooseTarget(title, source) {
    const body = h('<div class="col"><label>Find a named person<input class="input target-name" placeholder="Search names"></label><div class="target-results"></div><p class="danger-text" role="alert"></p></div>');
    let selected = null, seq = 0, timer;
    async function find() { const n=++seq; try { const r=await api('/people?limit=200&q='+encodeURIComponent($('.target-name',body).value)); if(n!==seq)return; const candidates=r.items.filter(p=>p.id!==source.id && p.owner===source.owner);$('.target-results',body).innerHTML=candidates.length?candidates.map(p=>`<label class="person-option"><input type="radio" name="target" value="${p.id}"><img src="${faceImage(p.cover)}" alt=""><span>${esc(p.name||'Unnamed person')} · ${num(p.photos)} photos</span></label>`).join(''):'<p class="muted">No other matching group. Give another group a name first.</p>'; $$('input[type=radio]',body).forEach(radio=>radio.onchange=()=>selected=+radio.value); } catch(e){$('.danger-text',body).textContent=e.message;} }
    $('.target-name',body).oninput=()=>{selected=null;clearTimeout(timer);timer=setTimeout(find,200);};find();
    const choice=await modal(title,body,[{label:'Cancel',value:null},{label:'Choose person',value:'ok',cls:'primary',validate:()=>{if(!selected){$('.danger-text',body).textContent='Select a person first.';return false;}return true;}}]);
    clearTimeout(timer);seq++;return choice==='ok'?selected:null;
  }

  async function mergePerson(person) {
    const target=await chooseTarget('Bring matching groups together',person);if(!target)return;
    try{await api(`/people/${person.id}/merge`,{target});location.hash='#/people?id='+target;toast('People groups merged. You can correct individual matches at any time.');}catch(e){fail(e);}
  }

  async function correct(fid) {
    const choice=await modal('Correct this match',h(`<div class="col"><img class="correction-preview" src="${faceImage(fid)}" alt="Face to correct"><p>Move this face out of this group, assign it to someone else, or remove a detection that isn’t a face. Your original photo stays in your library.</p></div>`),[{label:'Cancel'},{label:'Not a face',value:'ignore'},{label:'Choose person',value:'choose'},{label:'Different person',value:'split',cls:'primary'}]);
    if(!['ignore','choose','split'].includes(choice))return;
    try{let payload={};if(choice==='ignore')payload.ignore=true;if(choice==='choose'){const target=await chooseTarget('Who is this?',current);if(!target)return;payload.target=target;}const r=await api(`/faces/${fid}/correct`,payload);if(choice==='split'){location.hash='#/people?id='+r.person_id;}else{offset=0;load();}}catch(e){fail(e);}
  }

  async function celebrity(person) {
    const fid=person.faces[0]?.id;if(!fid)return;
    if(!capability){await modal('Celebrity suggestions',h('<div class="col"><p>Automatic celebrity suggestions use Amazon Rekognition. Connect an AWS account in the NAS app configuration to enable this optional feature.</p><p class="muted">Local face grouping and names work without it. No photos have been sent to a recognition service.</p></div>'),[{label:'Done',cls:'primary'}]);return;}
    const approved=await modal('Look for a celebrity match?',h(`<div class="col"><img class="correction-preview" src="${faceImage(fid)}" alt="Exact crop to send"><p>This sends <b>only the face crop shown above</b> to Amazon Rekognition. Use this for a photo you expect contains a public figure. AWS service charges and data handling apply.</p><p class="muted">You’ll review any suggested name before it is saved.</p></div>`),[{label:'Cancel'},{label:'Send crop and look up',value:'send',cls:'primary'}]);
    if(approved!=='send')return;
    const button=$('.celebrity-person',el);button.disabled=true;
    try{const r=await api(`/faces/${fid}/celebrity`,{consent:'send-this-crop-to-amazon-rekognition'});if(!r.suggestions.length){toast('No confident celebrity match found. You can add a name yourself.','info');return;}const s=r.suggestions[0];const pick=await modal('Review suggested name',h(`<div class="col"><h2>${esc(s.name)}</h2><p>Amazon Rekognition reports ${s.confidence}% confidence. This is a suggestion and may be wrong.</p></div>`),[{label:'Dismiss'},{label:'Review and save name',value:'save',cls:'primary'}]);if(pick==='save')await namePerson(person,s.name);}catch(e){fail(e);}finally{button.disabled=false;}
  }

  async function start() {try{await api('/people/index',{retry:true});poll(true);await refreshStatus();}catch(e){fail(e);}}
  $('.index-people',el).onclick=start;
  $('.select-people',el).onclick=()=>setSelecting(!selecting);
  $('.find-person',el).oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{offset=0;load();},200);};
  $('.privacy',el).onclick=async()=>{
    const answer=await modal('People stays on your NAS',h('<div class="col"><p>Face detection, matching, names and face crops are stored and processed on your NAS. Matches can be imperfect; correct or merge groups whenever needed.</p><p>Celebrity lookup is separate and only sends a selected crop after you approve it.</p><p class="muted">Removing People data clears names, groups and saved face crops for the selected libraries. Original photos are kept. Pause indexing first.</p></div>'),[{label:'Remove People data',value:'clear',cls:'danger'},{label:'Done',cls:'primary'}]);
    if(answer==='clear'){const confirm=await modal('Remove People data?',h('<p>Remove all names, groups and face crops in the selected libraries? This cannot be undone. You can scan the original photos again.</p>'),[{label:'Cancel'},{label:'Remove data',value:'yes',cls:'danger'}]);if(confirm==='yes'){try{await api('/people/clear',{});offset=0;await load();refreshStatus();}catch(e){fail(e);}}}
  };
  const off=on('changed',e=>{if(['faces','op','purge','rule','index'].includes(e.detail?.kind)){offset=0;load();refreshStatus();}});
  refreshStatus();load();
  return()=>{alive=false;version++;clearTimeout(searchTimer);clearTimeout(statusTimer);off();};
}
