// Smart search: natural-language bar + filter builder over the whole index, with bulk actions.
// Also serves "Large files" (#/large) as a preset.
import { $, $$, api, bytes, CAT_LABEL, esc, h, icon, parseSize, pickFolder, shortPath } from '../core.js';
import { resultList } from '../resultlist.js';

const SMART_LABEL = { junk: 'System junk', temp: 'Temp / partial', empty: 'Empty files', logs: 'Logs', installers: 'Installers', blurry: 'Blurry photos', dark: 'Dark photos', tiny: 'Tiny images', screenshots: 'Screenshots', old_large: 'Old & large', large_videos: 'Huge videos' };
const ts2date = (t) => { if (!t) return ''; const d = new Date(t * 1000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const date2ts = (s) => (s ? new Date(s + 'T00:00:00').getTime() / 1000 : null);

export function searchView(root, params) {
  const large = params.get('preset') === 'large';
  const f = {};
  let sort = params.get('sort') || 'size', order = params.get('order') || 'desc';
  if (params.get('q')) f.q = params.get('q');
  if (params.get('cat')) f.cat = params.get('cat').split(',');
  if (params.get('ext')) f.ext = params.get('ext').split(',');
  if (params.get('dir')) f.dir = params.get('dir');
  if (params.get('smart')) f.smart = params.get('smart');
  if (params.get('year')) { const y = +params.get('year'); f.after = new Date(y, 0, 1) / 1000; f.before = new Date(y + 1, 0, 1) / 1000; }
  if (large) f.min_size = 100 * 2 ** 20;

  const el = h(`<div class="view" style="display:flex;flex-direction:column">
    <div class="page-head"><div class="grow"><h1>${large ? 'Large files' : 'Smart search'}</h1>
      <p>${large ? 'The biggest space hogs on your NAS. Select and remove in bulk.' : 'Type what you want in plain English, or build a filter. Every result can be bulk-deleted or moved.'}</p></div></div>
    ${large ? `<div class="filters presets"><span class="muted">Larger than</span>${[['50 MB', 50], ['100 MB', 100], ['500 MB', 500], ['1 GB', 1024], ['4 GB', 4096], ['10 GB', 10240]].map(([l, v]) => `<button class="chip" data-v="${v}">${l}</button>`).join('')}</div>` : `
    <div class="search-box" style="max-width:none;margin-bottom:12px;flex:none">${icon('sparkles')}<input class="nl" placeholder='e.g. "photos from 2019 bigger than 5mb", "mkv videos over 2gb in Movies", "blurry photos", "pdf named invoice"'></div>
    <div class="understood muted" style="margin:-4px 0 10px;font-size:12.5px"></div>`}
    <div class="filters">
      <input class="input sm f-q" placeholder="Name contains… (or *.jpg)" style="width:200px">
      <div class="row cats" style="gap:5px">${Object.entries(CAT_LABEL).map(([k, v]) => `<button class="chip" data-c="${k}">${v.split(' ')[0]}</button>`).join('')}</div>
    </div>
    <div class="filters">
      <input class="input sm f-ext" placeholder="Extensions: jpg, png" style="width:150px">
      <input class="input sm f-min" placeholder="Min size (10 MB)" style="width:120px">
      <input class="input sm f-max" placeholder="Max size" style="width:100px">
      <span class="muted">Date</span><input type="date" class="input sm f-after" aria-label="Modified after"><span class="muted">–</span><input type="date" class="input sm f-before" aria-label="Modified before">
      <button class="btn sm f-dir">${icon('folder')}<span>Everywhere</span></button>
      <select class="input sm f-smart" aria-label="Smart filter"><option value="">Any kind</option>${Object.entries(SMART_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
      <label class="chk"><input type="checkbox" class="f-dupes"> Only duplicates</label>
      <button class="btn sm ghost f-reset">${icon('x')}Reset</button>
    </div></div>`);
  root.append(el);
  const list = resultList({ filter: f, sort, order, empty: 'Nothing matches these filters' });
  el.append(list.el);

  const fill = () => {
    $('.f-q', el).value = f.q || '';
    $('.f-ext', el).value = (f.ext || []).join(', ');
    $('.f-min', el).value = f.min_size ? bytes(f.min_size) : '';
    $('.f-max', el).value = f.max_size ? bytes(f.max_size) : '';
    $('.f-after', el).value = ts2date(f.after);
    $('.f-before', el).value = ts2date(f.before ? f.before - 86400 : null);
    $('.f-dir span', el).textContent = f.dir ? shortPath(f.dir) : 'Everywhere';
    $('.f-smart', el).value = f.smart || '';
    $('.f-dupes', el).checked = !!f.dupes;
    $$('.cats .chip', el).forEach((c) => c.classList.toggle('on', (f.cat || []).includes(c.dataset.c)));
    $$('.presets .chip', el).forEach((c) => c.classList.toggle('on', f.min_size === +c.dataset.v * 2 ** 20));
  };
  const apply = () => { for (const k of Object.keys(f)) if (f[k] == null || f[k] === '' || (Array.isArray(f[k]) && !f[k].length)) delete f[k]; list.setFilter({ ...f }, sort, order); fill(); };

  $('.f-q', el).onchange = (e) => { f.q = e.target.value.trim(); apply(); };
  $('.f-ext', el).onchange = (e) => { f.ext = e.target.value.split(/[\s,;]+/).map((x) => x.replace(/^\./, '').toLowerCase()).filter(Boolean); apply(); };
  $('.f-min', el).onchange = (e) => { f.min_size = e.target.value ? parseSize(e.target.value) : null; apply(); };
  $('.f-max', el).onchange = (e) => { f.max_size = e.target.value ? parseSize(e.target.value) : null; apply(); };
  $('.f-after', el).onchange = (e) => { f.after = date2ts(e.target.value); apply(); };
  $('.f-before', el).onchange = (e) => { f.before = e.target.value ? date2ts(e.target.value) + 86400 : null; apply(); };
  $('.f-smart', el).onchange = (e) => { f.smart = e.target.value; apply(); };
  $('.f-dupes', el).onchange = (e) => { f.dupes = e.target.checked || null; apply(); };
  $('.f-dir', el).onclick = async () => { const d = await pickFolder('Search inside folder', f.dir); if (d !== null) { f.dir = d; apply(); } };
  $('.f-reset', el).onclick = () => { for (const k of Object.keys(f)) delete f[k]; if (large) f.min_size = 100 * 2 ** 20; if ($('.nl', el)) $('.nl', el).value = ''; apply(); };
  $$('.cats .chip', el).forEach((c) => (c.onclick = () => {
    const s = new Set(f.cat || []);
    s.has(c.dataset.c) ? s.delete(c.dataset.c) : s.add(c.dataset.c);
    f.cat = [...s]; apply();
  }));
  $$('.presets .chip', el).forEach((c) => (c.onclick = () => { f.min_size = +c.dataset.v * 2 ** 20; sort = 'size'; order = 'desc'; apply(); }));

  const nl = $('.nl', el);
  async function runNL(text) {
    const r = await api('/nlq', { q: text });
    if (r.view === 'duplicates') { location.hash = '#/duplicates' + (r.filter.dir ? '?dir=' + encodeURIComponent(r.filter.dir) : ''); return; }
    if (r.view === 'similar') { location.hash = '#/similar'; return; }
    for (const k of Object.keys(f)) delete f[k];
    Object.assign(f, r.filter);
    sort = r.sort; order = r.order;
    const parts = [];
    if (f.cat) parts.push(f.cat.map((c) => CAT_LABEL[c]).join(' or '));
    if (f.ext) parts.push(f.ext.map((e) => '.' + e).join(', '));
    if (f.smart) parts.push(SMART_LABEL[f.smart]);
    if (f.min_size) parts.push('larger than ' + bytes(f.min_size));
    if (f.max_size) parts.push('smaller than ' + bytes(f.max_size));
    if (f.after) parts.push('from ' + ts2date(f.after));
    if (f.before) parts.push('before ' + ts2date(f.before));
    if (f.mtime_before) parts.push('not modified since ' + ts2date(f.mtime_before));
    if (f.dir) parts.push('in ' + shortPath(f.dir));
    if (f.q) parts.push(`name contains “${f.q}”`);
    $('.understood', el).innerHTML = parts.length ? `${icon('sparkles').replace('class="i ', 'style="width:13px;height:13px;vertical-align:-2px" class="i ')} Understood: <b style="color:var(--text)">${esc(parts.join(' · '))}</b>, sorted by ${sort === 'ts' ? 'date' : sort} ${order === 'asc' ? '↑' : '↓'}` : 'Showing everything — try adding a type, size or year.';
    apply();
  }
  if (nl) {
    nl.onkeydown = (e) => { if (e.key === 'Enter') runNL(nl.value); };
    if (params.get('nl')) { nl.value = params.get('nl'); runNL(params.get('nl')); }
  }
  fill();
}
