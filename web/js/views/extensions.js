// File types: counts and space per extension; open a type on its own page, or delete every file of chosen types.
import { $, $$, api, bytes, CAT_COLORS, CAT_LABEL, confirmDelete, date, esc, fail, h, icon, num, on, pickFolder, shortPath, THUMBABLE } from '../core.js';
import { donut } from '../charts.js';
import { resultList } from '../resultlist.js';
import { scopeBanner } from './categories.js';

const NONE = '~'; // stands for "no extension" in the page address
const PERSONAL = ['image', 'video', 'document', 'audio'];
const typesHref = (exts, scope) => `#/extensions/${exts.map((x) => encodeURIComponent(x || NONE)).join(',')}${scope ? '?dir=' + encodeURIComponent(scope) : ''}`;
const extLabel = (x) => (x ? '.' + x : 'no extension');
const personalWarning = (rows, scope) => {
  const risky = rows.filter((r) => PERSONAL.includes(r.cat));
  return risky.length ? `<div class="notice warn">${icon('alert')}<div>This deletes every <b>${esc(risky.map((r) => extLabel(r.ext)).join(', '))}</b> file${scope ? ` in <b>${esc(shortPath(scope))}</b>` : ' on the NAS'}. These are usually personal files.</div></div>` : '';
};

export function extensionsView(root, params, sub = []) {
  if (sub[0]) return typeView(root, sub[0].split(',').map((x) => decodeURIComponent(x)).map((x) => (x === NONE ? '' : x)), params.get('dir') || '');
  const st = { rows: [], sel: new Set(), sort: 'size', dir: -1, q: '', cat: '', scope: params.get('dir') || '' };
  const el = h(`<div class="view">
    <div class="page-head"><div class="grow"><h1>File types</h1><p>How many files of each type you have and how much space they take. Open a type to browse its files, or select types to delete them all at once.</p></div>
      <button class="btn scope">${icon('folder')}<span>Everywhere</span></button></div>
    ${scopeBanner()}
    <div class="grid g2 charts"><div class="card chart1"><h2>${icon('pie')}Space by type</h2></div><div class="card chart2"><h2>${icon('file')}Files by type</h2></div></div>
    <div class="filters"><input class="input sm q" placeholder="Filter types…" aria-label="Filter file types">
      <select class="input sm cat" aria-label="Category"><option value="">All categories</option>${Object.entries(CAT_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></div>
    <div class="card table-card"><table class="tbl"><thead><tr>
      <th style="width:34px"><input type="checkbox" class="all" aria-label="Select all file types"></th><th class="sort" data-k="ext">Type</th><th class="sort" data-k="cat">Category</th>
      <th class="sort r" data-k="count">Files</th><th class="sort r" data-k="size">Total size</th><th style="width:18%"><span class="sr-only">Share of space</span></th><th class="sort r" data-k="avg">Average</th><th class="sort r" data-k="max">Largest</th><th class="sort" data-k="newest">Newest</th><th><span class="sr-only">Open</span></th></tr></thead>
      <tbody><tr><td colspan="10"><div class="list-skel list">${'<div></div>'.repeat(6)}</div></td></tr></tbody></table></div>
    <div class="selbar pinned hidden"></div></div>`);
  root.append(el);

  async function load() {
    try {
      st.rows = await api('/extensions' + (st.scope ? '?dir=' + encodeURIComponent(st.scope) : ''));
    } catch (e) {
      $('tbody', el).innerHTML = `<tr><td colspan="10"><div class="empty">${icon('alert')}<div>Couldn’t load file types.</div><div class="muted small">${esc(e.message)}</div><button class="btn sm retry">${icon('refresh')}Try again</button></div></td></tr>`;
      $('.retry', el).onclick = load;
      return;
    }
    $('.scope span', el).textContent = st.scope ? shortPath(st.scope) : 'Everywhere';
    const top = [...st.rows].sort((a, b) => b.size - a.size);
    const rest = (arr, k) => arr.slice(10).reduce((a, x) => a + x[k], 0);
    const mk = (arr, k) => [...arr.slice(0, 10).map((x) => ({ label: x.ext ? '.' + x.ext : '(none)', value: x[k], color: CAT_COLORS[x.cat], onClick: () => drill([x.ext]) })), ...(arr.length > 10 ? [{ label: 'Other', value: rest(arr, k), color: '#555d6b' }] : [])];
    const c1 = $('.chart1', el), c2 = $('.chart2', el);
    c1.querySelector('.row')?.remove(); c2.querySelector('.row')?.remove();
    const totalSize = st.rows.reduce((a, x) => a + x.size, 0), totalCount = st.rows.reduce((a, x) => a + x.count, 0);
    c1.append(donut(mk(top, 'size'), { center: bytes(totalSize), centerSub: `${st.rows.length} types`, fmt: bytes }));
    c2.append(donut(mk([...st.rows].sort((a, b) => b.count - a.count), 'count'), { center: num(totalCount), centerSub: 'files', fmt: num }));
    table();
  }

  function table() {
    const max = Math.max(1, ...st.rows.map((r) => r.size));
    let rows = st.rows.filter((r) => (!st.q || r.ext.includes(st.q.toLowerCase().replace(/^\./, ''))) && (!st.cat || r.cat === st.cat));
    rows = rows.sort((a, b) => (typeof a[st.sort] === 'string' ? a[st.sort].localeCompare(b[st.sort]) : a[st.sort] - b[st.sort]) * st.dir);
    $('tbody', el).innerHTML = rows.length ? rows.map((r) => `<tr class="${st.sel.has(r.ext) ? 'sel' : ''}" data-e="${esc(r.ext)}">
      <td><input type="checkbox" ${st.sel.has(r.ext) ? 'checked' : ''} aria-label="Select ${esc(extLabel(r.ext))} files"></td>
      <td><span class="badge tint" style="--c:${CAT_COLORS[r.cat]}">${esc(r.ext ? '.' + r.ext : 'none')}</span></td>
      <td class="muted">${esc(CAT_LABEL[r.cat] || r.cat)}</td><td class="r num">${num(r.count)}</td><td class="r num"><b>${bytes(r.size)}</b></td>
      <td><div class="bar-track"><div class="bar-fill" style="width:${(100 * r.size) / max}%;background:${CAT_COLORS[r.cat]}"></div></div></td>
      <td class="r num muted">${bytes(r.avg)}</td><td class="r num muted">${bytes(r.max)}</td><td class="muted num">${date(r.newest)}</td>
      <td><a class="btn sm ghost view-type" href="${typesHref([r.ext], st.scope)}">Open${icon('right')}</a></td></tr>`).join('')
      : `<tr><td colspan="10"><div class="empty">${icon('file')}<div>${st.rows.length ? 'No file types match this filter' : 'No files here yet'}</div></div></td></tr>`;
    $$('tbody tr[data-e]', el).forEach((tr) => {
      const ext = tr.dataset.e;
      tr.onclick = (e) => {
        if (e.target.closest('.view-type')) return;
        st.sel.has(ext) ? st.sel.delete(ext) : st.sel.add(ext);
        table();
      };
      tr.ondblclick = (e) => { if (!e.target.closest('input, a')) location.hash = typesHref([ext], st.scope); };
    });
    $$('th.sort', el).forEach((th) => {
      th.classList.toggle('on', th.dataset.k === st.sort);
      th.onclick = () => { if (st.sort === th.dataset.k) st.dir *= -1; else { st.sort = th.dataset.k; st.dir = ['ext', 'cat'].includes(st.sort) ? 1 : -1; } table(); };
    });
    $('.all', el).checked = rows.length && rows.every((r) => st.sel.has(r.ext));
    $('.all', el).onchange = (e) => { rows.forEach((r) => (e.target.checked ? st.sel.add(r.ext) : st.sel.delete(r.ext))); table(); };
    selbar();
  }

  function selbar() {
    const sb = $('.selbar', el);
    const chosen = st.rows.filter((r) => st.sel.has(r.ext));
    sb.classList.toggle('hidden', !chosen.length);
    if (!chosen.length) return;
    const n = chosen.reduce((a, r) => a + r.count, 0), size = chosen.reduce((a, r) => a + r.size, 0);
    sb.innerHTML = `<span class="count">${chosen.length} type${chosen.length > 1 ? 's' : ''}</span><span class="muted">${esc(chosen.slice(0, 6).map((r) => '.' + (r.ext || 'none')).join(' '))}${chosen.length > 6 ? '…' : ''} · ${num(n)} files · ${bytes(size)}</span>
      <span class="grow"></span><a class="btn sm v" href="${typesHref(chosen.map((r) => r.ext), st.scope)}">${icon('eye')}Open files</a><button class="btn sm ghost clr">Clear</button>
      <button class="btn danger del">${icon('trash')}Delete all ${num(n)} files</button>`;
    $('.clr', sb).onclick = () => { st.sel.clear(); table(); };
    $('.del', sb).onclick = async () => {
      const filter = { ext: chosen.map((r) => r.ext), ...(st.scope ? { dir: st.scope } : {}) };
      const t = await confirmDelete({ filter, count: n, size, reason: 'by extension', extra: personalWarning(chosen, st.scope) });
      if (t) { st.sel.clear(); load(); }
    };
  }

  const openTypes = (exts) => { location.hash = typesHref(exts, st.scope); };
  const drill = (exts) => openTypes(exts);
  $('.q', el).oninput = (e) => { st.q = e.target.value; table(); };
  $('.cat', el).onchange = (e) => { st.cat = e.target.value; table(); };
  $('.scope', el).onclick = async () => {
    const d = await pickFolder('Only count files inside…', st.scope);
    if (d === null) return;
    st.scope = d || ''; st.sel.clear();
    history.replaceState(null, '', '#/extensions' + (st.scope ? '?dir=' + encodeURIComponent(st.scope) : ''));
    load();
  };
  load();
  return on('changed', load);
}

// One or more file types on their own page, as a list or as thumbnails.
function typeView(root, exts, scope) {
  const label = exts.map(extLabel).join(', ');
  const media = exts.every((x) => THUMBABLE.has(x));
  const el = h(`<div class="view fill">
    <div class="page-head"><a class="btn icon ghost" href="#/extensions${scope ? '?dir=' + encodeURIComponent(scope) : ''}" aria-label="Back to file types">${icon('left')}</a>
      <div class="grow"><h1>${esc(exts.length === 1 && exts[0] ? '.' + exts[0].toUpperCase() + ' files' : label)}</h1><p class="d">${scope ? `In <b>${esc(shortPath(scope))}</b>` : 'Everywhere on the NAS'}</p></div>
      <button class="btn danger all" disabled>${icon('trash')}Delete all</button></div>${scopeBanner()}</div>`);
  root.append(el);
  const filter = { ext: exts, ...(scope ? { dir: scope } : {}) };
  const list = resultList({ filter, sort: 'size', order: 'desc', mode: media ? 'grid' : 'list', id: media ? 'types-media' : 'types-other', empty: `No ${label} files${scope ? ' in this folder' : ''}` });
  el.append(list.el);
  let rows = [];
  const summary = async () => {
    try { rows = (await api('/extensions' + (scope ? '?dir=' + encodeURIComponent(scope) : ''))).filter((r) => exts.includes(r.ext)); } catch (e) { return fail(e); }
    const n = rows.reduce((a, r) => a + r.count, 0), size = rows.reduce((a, r) => a + r.size, 0);
    const cats = [...new Set(rows.map((r) => CAT_LABEL[r.cat] || r.cat))].join(', ');
    $('.d', el).innerHTML = `${cats ? esc(cats) + ' · ' : ''}${num(n)} ${n === 1 ? 'file' : 'files'} · ${bytes(size)} · ${scope ? `in <b>${esc(shortPath(scope))}</b>` : 'everywhere on the NAS'}`;
    $('.all', el).disabled = !n;
  };
  $('.all', el).onclick = async () => { list.selectAll(); if (!(await list.deleteSelected(personalWarning(rows, scope)))) list.clear(); };
  summary();
  const off = on('changed', summary);
  return () => { off(); list.destroy(); };
}
