// File types: counts and space per extension; drill in, or delete every file of chosen types.
import { $, $$, api, bytes, CAT_COLORS, CAT_LABEL, confirmBox, confirmDelete, date, esc, fail, h, icon, num, on, pickFolder, shortPath } from '../core.js';
import { donut } from '../charts.js';
import { resultList } from '../resultlist.js';

export function extensionsView(root, params) {
  const st = { rows: [], sel: new Set(), sort: 'size', dir: -1, q: '', cat: '', scope: params.get('dir') || '' };
  const el = h(`<div class="view">
    <div class="page-head"><div class="grow"><h1>File types</h1><p>How many files of each extension you have and how much space they take. Select types to review or delete them all at once.</p></div>
      <button class="btn scope">${icon('folder')}<span>Everywhere</span></button></div>
    <div class="grid g2" style="margin-bottom:16px"><div class="card chart1"><h3>${icon('pie')}Space by extension</h3></div><div class="card chart2"><h3>${icon('file')}Files by extension</h3></div></div>
    <div class="selbar hidden"></div>
    <div class="filters"><input class="input sm q" placeholder="Filter extensions…" style="width:180px">
      <select class="input sm cat"><option value="">All categories</option>${Object.entries(CAT_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></div>
    <div class="card" style="padding:0;overflow:auto;max-height:620px"><table class="tbl"><thead><tr>
      <th style="width:34px"><input type="checkbox" class="all"></th><th class="sort" data-k="ext">Extension</th><th class="sort" data-k="cat">Category</th>
      <th class="sort r" data-k="count">Files</th><th class="sort r" data-k="size">Total size</th><th style="width:18%"></th><th class="sort r" data-k="avg">Average</th><th class="sort r" data-k="max">Largest</th><th class="sort" data-k="newest">Newest</th><th></th></tr></thead><tbody></tbody></table></div>
    <div class="drill" style="margin-top:16px"></div></div>`);
  root.append(el);

  async function load() {
    try {
      st.rows = await api('/extensions' + (st.scope ? '?dir=' + encodeURIComponent(st.scope) : ''));
    } catch (e) { return fail(e); }
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
    $('tbody', el).innerHTML = rows.map((r) => `<tr class="${st.sel.has(r.ext) ? 'sel' : ''}" data-e="${esc(r.ext)}">
      <td><input type="checkbox" ${st.sel.has(r.ext) ? 'checked' : ''}></td>
      <td><span class="badge" style="background:${CAT_COLORS[r.cat]}22;color:${CAT_COLORS[r.cat]}">${esc(r.ext ? '.' + r.ext : '(none)')}</span></td>
      <td class="muted">${esc(CAT_LABEL[r.cat] || r.cat)}</td><td class="r num">${num(r.count)}</td><td class="r num"><b>${bytes(r.size)}</b></td>
      <td><div class="bar-track"><div class="bar-fill" style="width:${(100 * r.size) / max}%;background:${CAT_COLORS[r.cat]}"></div></div></td>
      <td class="r num muted">${bytes(r.avg)}</td><td class="r num muted">${bytes(r.max)}</td><td class="muted num">${date(r.newest)}</td>
      <td><button class="btn sm ghost view">${icon('eye')}View</button></td></tr>`).join('');
    $$('tbody tr', el).forEach((tr) => {
      const ext = tr.dataset.e;
      tr.onclick = (e) => {
        if (e.target.closest('.view')) return drill([ext]);
        st.sel.has(ext) ? st.sel.delete(ext) : st.sel.add(ext);
        table();
      };
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
      <span class="grow"></span><button class="btn sm v">${icon('eye')}Review files</button><button class="btn sm ghost clr">Clear</button>
      <button class="btn danger del">${icon('trash')}Delete all ${num(n)} files</button>`;
    $('.v', sb).onclick = () => drill(chosen.map((r) => r.ext));
    $('.clr', sb).onclick = () => { st.sel.clear(); table(); };
    $('.del', sb).onclick = async () => {
      const exts = chosen.map((r) => r.ext);
      const risky = chosen.filter((r) => ['image', 'video', 'document', 'audio'].includes(r.cat));
      if (risky.length && !(await confirmBox('Are you sure?', `You are about to delete every <b>${esc(risky.map((r) => '.' + r.ext).join(', '))}</b> file${st.scope ? ` in <b>${esc(shortPath(st.scope))}</b>` : ' on the NAS'}. These are usually personal files.`, 'Yes, continue', true))) return;
      const filter = { ext: exts, ...(st.scope ? { dir: st.scope } : {}) };
      const t = await confirmDelete({ filter, count: n, size, reason: 'by extension' });
      if (t) { st.sel.clear(); load(); $('.drill', el).innerHTML = ''; }
    };
  }

  function drill(exts) {
    const d = $('.drill', el);
    d.innerHTML = `<h3 style="margin:0 0 10px">${esc(exts.map((x) => '.' + (x || 'none')).join(', '))} files</h3>`;
    const list = resultList({ filter: { ext: exts, ...(st.scope ? { dir: st.scope } : {}) }, sort: 'size', order: 'desc', height: '560px' });
    d.append(list.el);
    d.scrollIntoView({ behavior: 'smooth' });
  }

  $('.q', el).oninput = (e) => { st.q = e.target.value; table(); };
  $('.cat', el).onchange = (e) => { st.cat = e.target.value; table(); };
  $('.scope', el).onclick = async () => { const d = await pickFolder('Only count files inside…', st.scope); st.scope = d || ''; st.sel.clear(); load(); };
  load();
  return on('changed', load);
}
