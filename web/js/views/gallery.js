// Timeline photo & video gallery with month sections, year scrubber, multi-select and lightbox.
import { $, $$, api, bytes, confirmDelete, dur, esc, fail, h, icon, num, pickFolder, runTask, shortPath, thumbUrl } from '../core.js';
import { lightbox } from '../lightbox.js';

const PAGE = 300;

export function galleryView(root, params) {
  let generation = 0, disposed = false;
  const st = { kind: params.get('kind') || 'all', dir: params.get('dir') || '', items: [], total: 0, pending: null, done: false, selecting: false, sel: new Map(), anchor: -1, tile: +localStorage.getItem('gal-tile') || 170 };
  const el = h(`<div class="view flush gallery-view"><div class="gallery-heading"><div><h1>Photos</h1><p>Your moments, together.</p></div><button class="btn select-mode" aria-pressed="false">Select</button></div><div class="fm-tools">
      <div class="seg kind"><button data-k="all">All</button><button data-k="image">Photos</button><button data-k="video">Videos</button></div>
      <button class="btn sm dirb" aria-label="Choose photo folder">${icon('folder')}<span>All folders</span></button>
      <span class="muted count"></span><span class="grow"></span>
      <div class="selinfo row"></div>
      <input type="range" class="sz" min="90" max="320" step="10" aria-label="Photo size" title="Photo size" style="width:110px">
    </div><div class="gal-wrap"><div class="gal-scroll"></div><div class="scrubber"></div></div></div>`);
  root.append(el);
  const scroll = $('.gal-scroll', el);
  $('.select-mode',el).onclick = () => { st.selecting = !st.selecting; if (!st.selecting) st.sel.clear(); refreshSel(); };
  scroll.style.setProperty('--tile', st.tile + 'px');
  $('.sz', el).value = st.tile;
  $('.sz', el).oninput = (e) => { st.tile = +e.target.value; scroll.style.setProperty('--tile', st.tile + 'px'); localStorage.setItem('gal-tile', st.tile); };

  const filter = () => ({ cat: st.kind === 'all' ? ['image', 'video'] : [st.kind], ...(st.dir ? { dir: st.dir } : {}) });
  const rememberLocation = () => { const query = new URLSearchParams(); if (st.kind !== 'all') query.set('kind',st.kind); if (st.dir) query.set('dir',st.dir); history.replaceState(null,'','#/gallery' + (query.size ? '?' + query : '')); };
  const monthKey = (ts) => { const d = new Date(ts * 1000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; };
  const monthLabel = (k) => { const [y, m] = k.split('-'); return new Date(+y, +m - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }); };

  async function reset() {
    const version = ++generation;
    st.items = []; st.total = 0; st.pending = null; st.done = false; st.anchor = -1; st.sel.clear(); scroll.innerHTML = ''; scroll.scrollTop = 0;
    scroll.setAttribute('aria-busy','true');
    $$('.kind button', el).forEach((b) => { b.classList.toggle('on', b.dataset.k === st.kind); b.setAttribute('aria-pressed',String(b.dataset.k === st.kind)); });
    $('.dirb span', el).textContent = st.dir ? shortPath(st.dir) : 'All folders';
    let tl;
    try { tl = await api('/timeline', { filter: filter() }); }
    catch(e) { if (!disposed && version === generation) { scroll.setAttribute('aria-busy','false'); scroll.innerHTML = '<div class="empty">Unable to load photos. Choose a filter to try again.</div>'; fail(e); } return; }
    if (disposed || version !== generation) return;
    const sc = $('.scrubber', el);
    sc.innerHTML = '';
    let lastY = null;
    for (const m of tl) {
      if (!m.month) continue;
      const [y, mo] = m.month.split('-');
      if (y !== lastY) { sc.append(h(`<div class="y" data-m="${m.month}">${y}</div>`)); lastY = y; }
      sc.append(h(`<div data-m="${m.month}" title="${num(m.count)} items">${new Date(+y, +mo - 1).toLocaleDateString(undefined, { month: 'short' })}</div>`));
    }
    $$('div[data-m]', sc).forEach((d) => (d.onclick = () => jump(d.dataset.m)));
    await more();
    if (disposed || version !== generation) return;
    scroll.setAttribute('aria-busy','false');
    refreshSel();
  }

  function more() {
    if (st.pending) return st.pending;
    if (disposed || st.done) return Promise.resolve();
    const version = generation;
    st.pending = api('/query', { filter: filter(), sort: 'ts', order: 'desc', limit: PAGE, offset: st.items.length }).then(r => {
      if (disposed || version !== generation) return;
      st.total = r.total;
      $('.count', el).textContent = `${num(r.total)} items · ${bytes(r.total_size)}`;
      const start = st.items.length;
      st.items.push(...r.items); st.done = st.items.length >= r.total || !r.items.length;
      append(start);
      if (!r.total) scroll.innerHTML = `<div class="empty">${icon('images')}<div>No photos or videos here yet</div></div>`;
    }).catch(e => { if (!disposed && version === generation) { st.done = true; fail(e); } }).finally(() => { if (version === generation) st.pending = null; });
    return st.pending;
  }

  function append(start) {
    for (let i = start; i < st.items.length; i++) {
      const it = st.items[i];
      const k = monthKey(it.ts);
      let sec = scroll.querySelector(`.gal-month[data-m="${k}"]`);
      if (!sec) {
        sec = h(`<section class="gal-month" data-m="${k}"><h4><span>${monthLabel(k)}</span><button class="btn sm ghost selm">${icon('selectAll')}Select month</button></h4><div class="gal-grid"></div></section>`);
        $('.selm', sec).onclick = () => {
          const idx = st.items.map((x, j) => [x, j]).filter(([x]) => monthKey(x.ts) === k);
          const allOn = idx.every(([x]) => st.sel.has(x.id));
          idx.forEach(([x]) => (allOn ? st.sel.delete(x.id) : st.sel.set(x.id, x)));
          refreshSel();
        };
        scroll.append(sec);
      }
      const t = h(`<div class="gtile${st.sel.has(it.id) ? ' sel' : ''}" data-i="${i}" role="button" tabindex="0" aria-label="${esc(it.name)}" aria-pressed="${st.sel.has(it.id)}"><img loading="lazy" src="${thumbUrl(it)}" alt="">
        <div class="ck">${icon('check')}</div>${it.cat === 'video' ? `<span class="vid">${icon('play')}${it.duration ? dur(it.duration) : bytes(it.size, 0)}</span>` : ''}</div>`);
      $('img', t).onerror = function () { this.replaceWith(h(`<div class="empty" style="padding:30% 0;font-size:11px">${esc(it.ext.toUpperCase())}</div>`)); };
      $('.gal-grid', sec).append(t);
    }
  }

  function refreshSel() {
    $$('.gtile', scroll).forEach((t) => { const selected = st.sel.has(st.items[+t.dataset.i].id); t.classList.toggle('sel',selected); t.setAttribute('aria-pressed',String(selected)); });
    scroll.classList.toggle('selecting', st.selecting || st.sel.size > 0);
    $('.select-mode',el).textContent = st.selecting ? 'Done' : 'Select';
    $('.select-mode',el).setAttribute('aria-pressed',String(st.selecting));
    selbar();
  }

  function selbar() {
    const n = st.sel.size;
    const size = [...st.sel.values()].reduce((a, x) => a + x.size, 0);
    const s = $('.selinfo', el);
    s.innerHTML = n ? `<b>${num(n)}</b><span class="muted">selected · ${bytes(size)}</span>
      <button class="btn sm mv">${icon('move')}Move</button><button class="btn sm dl">${icon('download')}Download</button>
      <button class="btn sm danger del">${icon('trash')}Delete</button><button class="btn sm ghost icon clr" aria-label="Clear photo selection">${icon('x')}</button>` : '';
    if (!n) return;
    $('.clr', s).onclick = () => { st.sel.clear(); refreshSel(); };
    $('.del', s).onclick = async () => {
      const t = await confirmDelete({ ids: [...st.sel.keys()], count: n, size });
      if (t?.status === 'done') reset();
    };
    $('.mv', s).onclick = async () => {
      const dest = await pickFolder('Move selected to…');
      if (dest && (await runTask(api('/move', { ids: [...st.sel.keys()], dest })))) reset();
    };
    $('.dl', s).onclick = () => { location.href = `/api/zip?name=photos&paths=${encodeURIComponent(JSON.stringify([...st.sel.values()].map((x) => x.path)))}`; };
  }

  async function jump(month) {
    let sec = scroll.querySelector(`.gal-month[data-m="${month}"]`);
    const version = generation;
    while (!sec && !st.done && !disposed && version === generation) { await more(); sec = scroll.querySelector(`.gal-month[data-m="${month}"]`); }
    sec?.scrollIntoView({ block: 'start' });
  }

  scroll.addEventListener('click', (e) => {
    const t = e.target.closest('.gtile');
    if (!t) return;
    const i = +t.dataset.i, it = st.items[i];
    if (e.shiftKey && st.anchor >= 0) {
      for (let k = Math.min(st.anchor, i); k <= Math.max(st.anchor, i); k++) st.sel.set(st.items[k].id, st.items[k]);
      refreshSel();
    } else if (st.selecting || e.ctrlKey || e.metaKey || e.target.closest('.ck') || st.sel.size) {
      st.sel.has(it.id) ? st.sel.delete(it.id) : st.sel.set(it.id, it);
      st.anchor = i;
      refreshSel();
    } else {
      let dirty = false;
      lightbox([...st.items], i, { onDeleted: () => (dirty = true), onClose: () => dirty && reset() });
      st.anchor = i;
    }
  });
  scroll.addEventListener('keydown',e => { if (e.target.matches('.gtile') && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); e.target.click(); } });
  scroll.addEventListener('scroll', () => { if (scroll.scrollTop + scroll.clientHeight > scroll.scrollHeight - 1200) more(); }, { passive: true });
  $$('.kind button', el).forEach((b) => (b.onclick = () => { st.kind = b.dataset.k; rememberLocation(); reset(); }));
  $('.dirb', el).onclick = async () => {
    const d = await pickFolder('Show photos from folder', st.dir);
    if (d !== null) { st.dir = d; rememberLocation(); reset(); }
  };
  const key = (e) => {
    if (document.querySelector('dialog[open],.modal-bg,.lightbox') || ['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) return;
    if ((e.ctrlKey || e.metaKey) && e.key === 'a') { e.preventDefault(); st.items.forEach((x) => st.sel.set(x.id, x)); refreshSel(); }
    if (e.key === 'Escape') { st.sel.clear(); refreshSel(); }
    if (e.key === 'Delete' && st.sel.size) $('.del', el)?.click();
  };
  document.addEventListener('keydown', key);
  reset();
  return () => { disposed = true; generation++; document.removeEventListener('keydown', key); };
}
