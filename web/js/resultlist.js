// Server-paged, virtualised list of indexed files with "select all N matching" bulk actions.
import {
  $, $$, api, avatar, bytes, confirmDelete, contextMenu, date, dur, dirname, esc, fail, fileIcon, h, icon, num, pickFolder, rawUrl,
  runTask, shortPath, state, THUMBABLE, thumbUrl,
} from './core.js';
import { lightbox } from './lightbox.js';

const ROW = 38;
const PAGE = 400;
const COLS = '34px minmax(220px,2fr) minmax(160px,1.4fr) 110px 150px';

export function resultList({ filter = {}, sort = 'size', order = 'desc', mode = 'list', height = null, guard = null, empty = 'No files match' } = {}) {
  const st = { filter, sort, order, mode, total: 0, totalSize: 0, pages: new Map(), loading: new Set(), sel: new Map(), all: false, excl: new Map(), anchor: -1, gen: 0 };
  const el = h(`<div class="panel-list" style="${height ? `height:${height}` : 'flex:1;min-height:320px'}">
    <div class="selbar-slot"></div>
    <div class="vl" tabindex="0"><div class="vl-head" style="grid-template-columns:${COLS}">
      <div><input type="checkbox" class="ck-all" title="Select all matching"></div>
      <div data-k="name">Name</div><div data-k="dir">Folder</div><div data-k="size" style="justify-content:flex-end">Size</div><div data-k="ts">Date</div></div>
      <div class="vl-inner"></div></div>
    <div class="status"></div></div>`);
  const vl = $('.vl', el), inner = $('.vl-inner', el), head = $('.vl-head', el);

  const isSel = (it) => (st.all ? !st.excl.has(it.id) : st.sel.has(it.id));
  const selCount = () => (st.all ? st.total - st.excl.size : st.sel.size);
  const selSize = () => {
    if (!st.all) return [...st.sel.values()].reduce((a, x) => a + x.size, 0);
    return st.totalSize - [...st.excl.values()].reduce((a, x) => a + x.size, 0);
  };
  const at = (i) => st.pages.get(Math.floor(i / PAGE))?.[i % PAGE];

  async function fetchPage(p) {
    const key = `${st.gen}:${p}`;
    if (st.pages.has(p) || st.loading.has(key)) return;
    st.loading.add(key);
    const gen = st.gen;
    try {
      const r = await api('/query', { filter: st.filter, sort: st.sort, order: st.order, limit: PAGE, offset: p * PAGE });
      if (gen !== st.gen) return;
      st.total = r.total; st.totalSize = r.total_size;
      st.pages.set(p, r.items);
      paint(); status();
    } catch (e) { if (gen === st.gen) { fail(e); inner.innerHTML = '<div class="empty">Couldn’t load results. Change a filter or try again.</div>'; } } finally { st.loading.delete(key); }
  }

  function geometry() {
    if (st.mode === 'list') return { cols: 1, rh: ROW, top: 32 };
    const W = vl.clientWidth - 16, t = 170;
    const cols = Math.max(1, Math.floor(W / (t + 8)));
    return { cols, rh: (W - (cols - 1) * 8) / cols + 8, top: 8, tw: (W - (cols - 1) * 8) / cols };
  }

  function paint() {
    const g = geometry();
    head.classList.toggle('hidden', st.mode !== 'list');
    const rows = Math.ceil(st.total / g.cols);
    if (!st.total && st.pages.size) {
      inner.style.height = 'auto';
      inner.innerHTML = `<div class="empty">${icon('search')}<div>${esc(empty)}</div></div>`;
      return;
    }
    inner.style.height = rows * g.rh + 16 + 'px';
    const top = Math.max(0, vl.scrollTop - (st.mode === 'list' ? 32 : 0));
    const r0 = Math.max(0, Math.floor(top / g.rh) - 3), r1 = Math.min(rows, Math.ceil((top + vl.clientHeight) / g.rh) + 3);
    const need = new Set();
    const html = [];
    for (let r = r0; r < r1; r++) for (let c = 0; c < g.cols; c++) {
      const i = r * g.cols + c;
      if (i >= st.total) break;
      const it = at(i);
      if (!it) { need.add(Math.floor(i / PAGE)); continue; }
      const s = isSel(it) ? ' sel' : '';
      if (st.mode === 'list') {
        html.push(`<div class="vrow${s}" data-i="${i}" style="top:${r * ROW}px;grid-template-columns:${COLS}">
          <div><input type="checkbox" ${s ? 'checked' : ''} tabindex="-1"></div>
          <div class="fname">${fileIcon(it)}<span class="ellipsis" title="${esc(it.name)}">${esc(it.name)}</span>${it.width ? `<span class="faint" style="font-size:11.5px">${it.width}×${it.height}</span>` : ''}</div>
          <div class="muted ellipsis mono row" style="gap:6px" title="${esc(it.dir)}">${it.owner && (!state.scope || state.scope.length > 1) ? avatar(it.owner) : ''}<span class="ellipsis">${esc(shortPath(it.dir))}</span></div>
          <div class="num" style="text-align:right">${bytes(it.size)}</div><div class="muted num">${date(it.ts)}</div></div>`);
      } else {
        const th = THUMBABLE.has(it.ext) ? `<img loading="lazy" src="${thumbUrl(it)}" onerror="this.style.display='none'">` : fileIcon(it, true);
        html.push(`<div class="tile${s}" data-i="${i}" style="top:${g.top + r * g.rh}px;left:${8 + c * (g.tw + 8)}px;width:${g.tw}px;height:${g.rh - 8}px">
          <div class="ck">${icon('check')}</div><div class="th">${th}${it.duration ? `<span class="vid" style="position:absolute;right:6px;bottom:6px;background:rgba(0,0,0,.5);color:#fff;border-radius:7px;padding:1px 6px;font-size:11px">${dur(it.duration)}</span>` : ''}</div><div class="nm">${esc(it.name)}</div><div class="meta">${bytes(it.size)}${it.width && it.cat === 'video' ? ` · ${it.height >= 2000 || it.width >= 3800 ? '4K' : it.height >= 1000 || it.width >= 1900 ? 'HD' : 'SD'}` : ''}</div></div>`);
      }
    }
    inner.innerHTML = html.join('');
    need.forEach(fetchPage);
  }

  function status() {
    const n = selCount();
    $('.ck-all', el).checked = st.all && !st.excl.size;
    $('.ck-all', el).indeterminate = n > 0 && !(st.all && !st.excl.size);
    $('.status', el).innerHTML = `<span><b style="color:var(--text)">${num(st.total)}</b> files · ${bytes(st.totalSize)}</span>${n ? `<span style="color:var(--text)">${num(n)} selected · ${bytes(selSize())}</span>` : ''}
      <span class="grow"></span><div class="seg" style="transform:scale(.85);transform-origin:right"><button data-m="list" class="${st.mode === 'list' ? 'on' : ''}">${icon('list')}</button><button data-m="grid" class="${st.mode === 'grid' ? 'on' : ''}">${icon('grid')}</button></div>`;
    $$('.status .seg button', el).forEach((b) => (b.onclick = () => { st.mode = b.dataset.m; vl.scrollTop = 0; paint(); status(); }));
    const slot = $('.selbar-slot', el);
    if (!n) { slot.innerHTML = ''; return; }
    slot.innerHTML = `<div class="row wrap" style="gap:8px;padding:9px 12px;border-bottom:1px solid var(--line);background:var(--panel2)">
      <b>${num(n)}</b> selected <span class="muted">· ${bytes(selSize())}</span>
      ${!st.all && st.total > n ? `<button class="btn sm ghost s-all">${icon('selectAll')}Select all ${num(st.total)} matching</button>` : ''}
      <span class="grow"></span>
      <button class="btn sm s-move">${icon('move')}Move to…</button><button class="btn sm s-copy">${icon('copy')}Copy to…</button>
      ${n <= 2000 ? `<button class="btn sm s-dl">${icon('download')}Download</button>` : ''}
      <button class="btn sm danger s-del">${icon('trash')}Delete ${num(n)}</button><button class="btn sm ghost icon s-clr" title="Clear selection">${icon('x')}</button></div>`;
    $('.s-all', slot)?.addEventListener('click', () => { st.all = true; st.excl.clear(); st.sel.clear(); paint(); status(); });
    $('.s-clr', slot).onclick = () => api_.clear();
    $('.s-del', slot).onclick = () => api_.deleteSelected();
    $('.s-move', slot).onclick = () => transfer(false);
    $('.s-copy', slot).onclick = () => transfer(true);
    $('.s-dl', slot)?.addEventListener('click', async () => {
      const ids = await selectedIds();
      const paths = ids.length <= 2000 ? await idsToPaths(ids) : [];
      if (paths.length === 1) location.href = `/api/raw?id=${ids[0]}&download=1`;
      else location.href = `/api/zip?paths=${encodeURIComponent(JSON.stringify(paths))}&name=selection`;
    });
  }

  async function selectedIds() {
    if (!st.all) return [...st.sel.keys()];
    const r = await api('/query/ids', { filter: st.filter });
    return r.ids.filter((i) => !st.excl.has(i));
  }
  async function idsToPaths(ids) {
    const r = await api('/query', { filter: { ids }, limit: ids.length });
    return r.items.map((x) => x.path);
  }
  async function transfer(copy) {
    const dest = await pickFolder(copy ? 'Copy selected to…' : 'Move selected to…');
    if (!dest) return;
    const ids = await selectedIds();
    const t = await runTask(api('/move', { ids, dest, copy }));
    if (t) api_.reload();
  }

  function toggle(i, ev) {
    const it = at(i);
    if (!it) return;
    const set = (x, on) => {
      if (st.all) on ? st.excl.delete(x.id) : st.excl.set(x.id, x);
      else on ? st.sel.set(x.id, x) : st.sel.delete(x.id);
    };
    if (ev.shiftKey && st.anchor >= 0) {
      for (let k = Math.min(st.anchor, i); k <= Math.max(st.anchor, i); k++) { const x = at(k); if (x) set(x, true); }
    } else set(it, !isSel(it));
    st.anchor = i;
    paint(); status();
  }

  inner.addEventListener('mousedown', (ev) => {
    const r = ev.target.closest('[data-i]');
    if (r) { ev.preventDefault(); toggle(+r.dataset.i, ev); }
  });
  inner.addEventListener('dblclick', (ev) => {
    const r = ev.target.closest('[data-i]');
    if (!r) return;
    const i = +r.dataset.i, it = at(i);
    if (['image', 'video', 'audio'].includes(it.cat) || it.ext === 'pdf') {
      const page = st.pages.get(Math.floor(i / PAGE)).filter((x) => ['image', 'video', 'audio'].includes(x.cat) || x.ext === 'pdf');
      lightbox(page, page.indexOf(it), { onDeleted: () => api_.reload() });
    } else location.hash = '#/files?path=' + encodeURIComponent(dirname(it.path));
  });
  inner.addEventListener('contextmenu', (ev) => {
    const r = ev.target.closest('[data-i]');
    if (!r) return;
    ev.preventDefault();
    const it = at(+r.dataset.i);
    contextMenu(ev.clientX, ev.clientY, [
      { label: 'Open containing folder', icon: 'folderOpen', run: () => (location.hash = '#/files?path=' + encodeURIComponent(it.dir)) },
      { label: 'Download', icon: 'download', run: () => (location.href = rawUrl(it, true)) },
      { label: 'Open in new tab', icon: 'expand', run: () => window.open(rawUrl(it), '_blank') },
      '-',
      { label: 'Delete this file', icon: 'trash', danger: true, run: async () => { const t = await confirmDelete({ ids: [it.id], count: 1, size: it.size, guard }); if (t) api_.reload(); } },
    ]);
  });
  vl.addEventListener('scroll', () => paint(), { passive: true });
  const resizeObserver = new ResizeObserver(() => paint()); resizeObserver.observe(vl);
  vl.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') { e.preventDefault(); st.all = true; st.excl.clear(); st.sel.clear(); paint(); status(); }
    if (e.key === 'Delete' && selCount()) { e.preventDefault(); api_.deleteSelected(); }
    if (e.key === 'Escape') api_.clear();
  });
  $('.ck-all', el).onchange = (e) => { if (e.target.checked) { st.all = true; st.excl.clear(); st.sel.clear(); } else api_.clear(); paint(); status(); };
  $$('[data-k]', head).forEach((d) => (d.onclick = () => {
    const k = d.dataset.k;
    if (st.sort === k) st.order = st.order === 'asc' ? 'desc' : 'asc'; else { st.sort = k; st.order = k === 'name' || k === 'dir' ? 'asc' : 'desc'; }
    api_.reload();
  }));
  function markSort() {
    $$('[data-k]', head).forEach((d) => {
      d.querySelector('svg')?.remove();
      if (d.dataset.k === st.sort) d.insertAdjacentHTML('beforeend', icon(st.order === 'asc' ? 'up' : 'down').replace('class="i ', 'style="width:13px;height:13px" class="i '));
    });
  }

  const api_ = {
    el,
    destroy() { st.gen++; resizeObserver.disconnect(); },
    get state() { return st; },
    setFilter(f, sort, order) { st.filter = f; if (sort) st.sort = sort; if (order) st.order = order; this.clear(false); this.reload(); },
    reload() {
      st.gen++; st.pages.clear(); st.total = 0; st.totalSize = 0;
      vl.scrollTop = 0; markSort();
      inner.innerHTML = '<div class="empty"><div class="spin" style="margin:0 auto"></div></div>';
      fetchPage(0);
    },
    clear(repaint = true) { st.all = false; st.sel.clear(); st.excl.clear(); if (repaint) { paint(); status(); } },
    async deleteSelected() {
      const n = selCount();
      if (!n) return;
      const payload = st.all && !st.excl.size ? { filter: st.filter } : { ids: await selectedIds() };
      const t = await confirmDelete({ ...payload, count: n, size: selSize(), guard });
      if (t) { this.clear(false); this.reload(); }
      return t;
    },
    selectAll() { st.all = true; st.excl.clear(); st.sel.clear(); paint(); status(); },
  };
  api_.reload();
  return api_;
}
