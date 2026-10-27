// Exact duplicates: auto-select by rule across ALL groups, review exceptions, delete in one click.
import { $, $$, api, avatar, bytes, CAT_LABEL, confirmDelete, date, esc, fail, h, icon, num, on, ownerChip, pickFolder, shortPath, state, THUMBABLE, thumbUrl, toast } from '../core.js';
import { scopeBanner } from './categories.js';
import { lightbox } from '../lightbox.js';

const KEEP = [
  ['recommended', 'Keep the recommended copy'],
  ['oldest', 'Keep the oldest copy'], ['newest', 'Keep the newest copy'], ['shortest_path', 'Keep the shortest path'],
  ['longest_path', 'Keep the deepest path'], ['shortest_name', 'Keep the shortest file name'],
];

export function duplicatesView(root, params) {
  const st = { filter: params.get('dir') ? { dir: params.get('dir') } : {}, sort: 'wasted', groups: [], offset: 0, done: false, sel: new Map(), keep: 'recommended', prefer: '', only: '', perUser: localStorage.getItem('dup-across') !== '1' };
  const el = h(`<div class="view">
    <div class="page-head"><div class="grow"><h1>Duplicates</h1><p class="sum">Exact byte-for-byte copies, verified with a full content hash.</p></div></div>
    ${scopeBanner()}
    <div class="card" style="margin-bottom:14px">
      <h3>${icon('wand')}Smart select<span class="right row" style="gap:10px;font-size:13px"><span class="muted">Within each user</span>
        <label class="switch" title="On: only copies owned by the same user count as duplicates. Off: compare across the selected users."><input type="checkbox" class="peruser"><span></span></label></span></h3>
      <div class="row wrap" style="gap:10px">
        <select class="input keep">${KEEP.map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select>
        <button class="btn prefer">${icon('star')}<span>Prefer keeping files in…</span></button>
        <button class="btn only">${icon('trash')}<span>Only delete copies in…</span></button>
        <button class="btn primary auto">${icon('wand')}Auto-select duplicates</button>
        <span class="grow"></span>
        <button class="btn ghost clear">${icon('x')}Clear selection</button>
      </div>
      <div class="faint" style="font-size:12.5px;margin-top:10px">Example: keep the copies in <b>Photos</b>, delete the ones in <b>Backup</b> and <b>WhatsApp</b> — choose "Prefer keeping files in Photos", then Auto-select. A safety lock always keeps one copy of every file.</div>
    </div>
    <div class="selbar hidden"></div>
    <div class="filters">
      <select class="input sm f-cat"><option value="">All types</option>${Object.entries(CAT_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
      <select class="input sm f-min"><option value="">Any size</option><option value="102400">≥ 100 KB</option><option value="1048576">≥ 1 MB</option><option value="10485760">≥ 10 MB</option><option value="104857600">≥ 100 MB</option><option value="1073741824">≥ 1 GB</option></select>
      <button class="btn sm f-dir">${icon('folder')}<span>${st.filter.dir ? esc(shortPath(st.filter.dir)) : 'All folders'}</span></button>
      <span class="grow"></span><span class="muted">Sort</span>
      <select class="input sm f-sort"><option value="wasted">Most wasted space</option><option value="count">Most copies</option><option value="size">Largest file</option></select>
    </div>
    <div class="groups"></div><div class="more-slot" style="text-align:center;padding:10px"></div></div>`);
  root.append(el);

  const sum = () => [...st.sel.values()].reduce((a, x) => a + x.size, 0);

  function selbar() {
    const sb = $('.selbar', el);
    sb.classList.toggle('hidden', !st.sel.size);
    if (!st.sel.size) return;
    sb.innerHTML = `${icon('trash')}<span class="count">${num(st.sel.size)} copies selected</span><span class="muted">· frees ${bytes(sum())}</span><span class="grow"></span>
      <button class="btn ghost sm clr">Clear</button><button class="btn danger go">${icon('trash')}Delete ${num(st.sel.size)} duplicates</button>`;
    $('.clr', sb).onclick = () => { st.sel.clear(); paintSel(); };
    $('.go', sb).onclick = async () => {
      const t = await confirmDelete({ ids: [...st.sel.keys()], count: st.sel.size, size: sum(), guard: st.perUser ? 'dupes' : 'dupes_all', reason: 'duplicates' });
      if (t?.status === 'done') { st.sel.clear(); reload(); }
    };
  }

  function paintSel() {
    $$('.gfile', el).forEach((r) => {
      const on = st.sel.has(+r.dataset.id);
      r.classList.toggle('del', on);
      $('input', r).checked = on;
      $('.tag', r).innerHTML = on ? '<span class="badge danger">delete</span>' : '<span class="badge ok">keep</span>';
    });
    selbar();
  }

  function groupEl(g) {
    const f0 = g.files[0];
    const thumb = THUMBABLE.has(f0.ext) ? `<img class="group-thumb" loading="lazy" src="${thumbUrl(f0)}" data-fallback="hide">` : `<div class="group-thumb" style="display:grid;place-items:center">${icon('file')}</div>`;
    const el2 = h(`<div class="group"><div class="group-head">${thumb}<div class="grow" style="min-width:0"><div class="ellipsis" style="font-weight:600">${esc(f0.name)}</div>
      <div class="muted" style="font-size:12.5px">${num(g.count)} copies × ${bytes(g.size)} · <span class="danger-text">${bytes(g.wasted)} wasted</span></div></div>
      ${g.owner ? ownerChip(g.owner) : ''}
      <button class="btn sm ghost kf" title="${esc(g.recommendation||'Keep one copy')}">Keep recommended copy</button></div>
      ${g.files.map((f) => `<div class="gfile" data-id="${f.id}"><input type="checkbox"><div class="p ellipsis mono row" style="gap:6px" title="${esc(f.path)}">${g.owner ? '' : avatar(f.owner)}<span class="ellipsis">${esc(shortPath(f.path))}</span></div>
        <span class="muted num">${date(f.mtime)}${f.id===g.recommended_id?' · recommended':''}</span><span class="tag"></span><button class="btn sm ghost icon op" title="Open folder">${icon('folderOpen')}</button></div>`).join('')}<p class="muted" style="padding:10px 16px;font-size:12px">${esc(g.recommendation||'One copy is always kept.')} Recycling checks that the kept copy is still available and unchanged.</p></div>`);
    $$('.gfile', el2).forEach((r) => {
      const f = g.files.find((x) => x.id === +r.dataset.id);
      r.onclick = (e) => {
        if (e.target.closest('.op')) { location.hash = '#/files?path=' + encodeURIComponent(f.dir); return; }
        if (st.sel.has(f.id)) st.sel.delete(f.id);
        else {
          const others = g.files.filter((x) => x.id !== f.id && !st.sel.has(x.id));
          if (!others.length) return toast('At least one copy must be kept', 'info');
          st.sel.set(f.id, f);
        }
        paintSel();
      };
    });
    $('.group-thumb', el2).onclick = () => THUMBABLE.has(f0.ext) && lightbox(g.files, 0);
    $('.kf', el2).onclick = () => { g.files.forEach(x => (x.id===(g.recommended_id||f0.id) ? st.sel.delete(x.id) : st.sel.set(x.id,x))); paintSel(); };
    return el2;
  }

  async function page() {
    const box = $('.more-slot', el);
    box.innerHTML = '<div class="spin" style="margin:auto"></div>';
    try {
      const r = await api('/duplicates', { filter: st.filter, sort: st.sort, limit: 40, offset: st.offset, per_user: st.perUser });
      $('.sum', el).innerHTML = r.groups ? `<b style="color:var(--text)">${num(r.groups)}</b> files have copies · <b style="color:var(--text)">${num(r.extra_files)}</b> extra copies waste <b class="danger-text">${bytes(r.wasted)}</b>`
        : 'No duplicates found' + (state_running() ? ' yet — hashing is still running.' : '. Nice and tidy!');
      $('.sum', el).innerHTML += st.perUser ? ' <span class="badge accent">within each user</span>' : ' <span class="badge warn">across users</span>';
      const gbox = $('.groups', el);
      if (!r.groups && !st.offset) gbox.innerHTML = `<div class="empty">${icon('check')}<div>No duplicates here</div></div>`;
      r.items.forEach((g) => gbox.append(groupEl(g)));
      st.offset += r.items.length;
      st.done = st.offset >= r.groups;
      paintSel();
      box.innerHTML = st.done ? '' : `<button class="btn">Load more groups (${num(r.groups - st.offset)} left)</button>`;
      if (!st.done) box.firstElementChild.onclick = page;
    } catch (e) { fail(e); box.innerHTML = ''; }
  }
  const state_running = () => document.querySelector('.task-indicator');

  function reload() { st.offset = 0; $('.groups', el).innerHTML = ''; page(); }

  $('.peruser', el).checked = st.perUser;
  $('.peruser', el).onchange = (e) => {
    st.perUser = e.target.checked;
    localStorage.setItem('dup-across', st.perUser ? '0' : '1');
    st.sel.clear();
    if (!st.perUser && (!state.scope || state.scope.length > 1)) toast('Comparing across users: a file counts as a duplicate even if another user owns the copy.', 'info', 6000);
    reload();
  };
  $('.keep', el).onchange = (e) => (st.keep = e.target.value);
  $('.prefer', el).onclick = async () => {
    const d = await pickFolder('Prefer keeping copies inside…', st.prefer);
    st.prefer = d || '';
    $('.prefer span', el).textContent = st.prefer ? 'Keep in: ' + shortPath(st.prefer) : 'Prefer keeping files in…';
    $('.prefer', el).classList.toggle('on', !!st.prefer);
  };
  $('.only', el).onclick = async () => {
    const d = await pickFolder('Only delete copies inside…', st.only);
    st.only = d || '';
    $('.only span', el).textContent = st.only ? 'Delete only in: ' + shortPath(st.only) : 'Only delete copies in…';
    $('.only', el).classList.toggle('on', !!st.only);
  };
  $('.auto', el).onclick = async () => {
    try {
      const r = await api('/duplicates/autoselect', { filter: st.filter, keep: st.keep, prefer_dir: st.prefer, only_in_dir: st.only, per_user: st.perUser });
      st.sel.clear();
      for (const [id, size] of r.items) st.sel.set(id, { id, size });
      paintSel();
      toast(`Selected <b>${num(r.items.length)}</b> duplicate copies across ${num(r.groups)} groups · ${bytes(r.size)}`);
    } catch (e) { fail(e); }
  };
  $('.clear', el).onclick = () => { st.sel.clear(); paintSel(); };
  $('.f-cat', el).onchange = (e) => { st.filter.cat = e.target.value || undefined; reload(); };
  $('.f-min', el).onchange = (e) => { st.filter.min_size = +e.target.value || undefined; reload(); };
  $('.f-sort', el).onchange = (e) => { st.sort = e.target.value; reload(); };
  $('.f-dir', el).onclick = async () => {
    const d = await pickFolder('Only groups touching folder…', st.filter.dir);
    st.filter.dir = d || undefined;
    $('.f-dir span', el).textContent = d ? shortPath(d) : 'All folders';
    reload();
  };
  page();
  return on('indexed', reload);
}
