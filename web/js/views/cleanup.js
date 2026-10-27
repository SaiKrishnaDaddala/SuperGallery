// Smart cleanup: junk, temp/partial downloads, empty files & folders, blurry/dark/tiny photos, old giants.
import { $, $$, api, bytes, confirmBox, esc, fail, h, icon, num, on, runTask, shortPath } from '../core.js';
import { resultList } from '../resultlist.js';

const ICONS = { junk: 'broom', temp: 'hourglass', empty: 'file', logs: 'list', installers: 'package', blurry: 'blur', dark: 'moon', tiny: 'minimize', screenshots: 'monitor', old_large: 'archive', large_videos: 'film', empty_folders: 'folder' };

export function cleanupView(root, params, sub) {
  const key = sub[0];
  const el = h('<div class="view" style="display:flex;flex-direction:column"></div>');
  root.append(el);
  if (key === 'empty_folders') return emptyFolders(el);
  if (key) return category(el, key);

  el.innerHTML = `<div class="page-head"><div class="grow"><h1>Cleanup categories</h1><p>Browse suggestions by type. Review files and select what you no longer need.</p></div></div>
    <div class="grid g3 cards"></div>`;
  api('/cleanup').then((r) => {
    const cards = [...r.categories, { key: 'empty_folders', title: 'Empty folders', desc: 'Folders with no files anywhere inside', count: r.empty_folders, size: 0 }];
    for (const c of cards) {
      const card = h(`<a class="card cleanup-card" href="#/cleanup/${c.key}" style="color:inherit"><div class="kpi">
        <div class="ic ${c.key === 'blurry' || c.key === 'dark' ? 'amber' : ''}">${icon(ICONS[c.key] || 'file')}</div>
        <div class="grow"><div style="font-weight:600">${esc(c.title)}</div><div class="muted" style="font-size:12.5px">${esc(c.desc)}</div></div></div>
        <div class="row" style="margin-top:14px"><span class="v" style="font-size:20px;font-weight:700">${num(c.count)}</span><span class="muted">${c.key === 'empty_folders' ? 'folders' : 'files'}</span><span class="grow"></span>
        ${c.size ? `<b>${bytes(c.size)}</b>` : ''}</div></a>`);
      if (!c.count) card.classList.add('is-empty');
      $('.cards', el).append(card);
    }
  }).catch(fail);
  return on('changed', () => window.dispatchEvent(new HashChangeEvent('hashchange')));
}

function category(el, key) {
  const blur = +(localStorage.getItem('blur') || 40);
  el.innerHTML = `<div class="page-head"><a class="btn ghost icon" href="#/cleanup" aria-label="Back to cleanup categories">${icon('left')}</a><div class="grow"><h1 class="t">Review files</h1><p class="d">Loading this category…</p></div>
    ${key === 'blurry' ? `<div class="row"><span class="muted">Sensitivity</span><input type="range" class="bl" min="10" max="120" step="5" value="${blur}"><span class="blv muted num">${blur}</span></div>` : ''}
    <button class="btn all" disabled>${icon('selectAll')}Select all</button></div>`;
  const list = resultList({ filter: { smart: key, blur }, sort: 'size', order: 'desc', mode: ['blurry', 'dark', 'tiny', 'screenshots'].includes(key) ? 'grid' : 'list', empty: 'No files in this category' });
  el.append(list.el);
  let summaryVersion = 0;
  const updateSummary = (sensitivity) => {
    const version = ++summaryVersion;
    $('.all', el).disabled = true;
    return api('/cleanup?blur=' + sensitivity).then((r) => {
    if (version !== summaryVersion) return;
    const c = r.categories.find((x) => x.key === key);
    if (!c) return;
    $('.t', el).textContent = c.title;
    $('.d', el).textContent = `${c.desc} · ${num(c.count)} files · ${bytes(c.size)}`;
    $('.all', el).disabled = !c.count;
    }).catch(fail);
  };
  updateSummary(blur);
  $('.all', el).onclick = () => list.selectAll();
  const bl = $('.bl', el);
  if (bl) {
    bl.oninput = () => ($('.blv', el).textContent = bl.value);
    bl.onchange = () => { localStorage.setItem('blur', bl.value); list.setFilter({ smart: key, blur: +bl.value }); updateSummary(+bl.value); };
  }
}

function emptyFolders(el) {
  el.innerHTML = `<div class="page-head"><a class="btn ghost icon" href="#/cleanup">${icon('left')}</a><div class="grow"><h1>Empty folders</h1><p class="d">Folders that contain no files at all (sub-folders included).</p></div>
    <button class="btn danger all">${icon('trash')}Remove all</button></div><div class="card" style="padding:0"><div class="lst"></div></div>`;
  let rows = [];
  const sel = new Set();
  const draw = () => {
    $('.lst', el).innerHTML = rows.length ? rows.map((r) => `<label class="list-row" style="padding:8px 14px;cursor:pointer"><input type="checkbox" data-p="${esc(r.path)}" ${sel.has(r.path) ? 'checked' : ''}>${icon('folder')}<span class="mono grow ellipsis">${esc(shortPath(r.path))}</span>
      <a class="btn sm ghost" href="#/files?path=${encodeURIComponent(r.path)}">${icon('folderOpen')}</a></label>`).join('') : `<div class="empty">${icon('check')}<div>No empty folders</div></div>`;
    $$('input[data-p]', el).forEach((i) => (i.onchange = () => { i.checked ? sel.add(i.dataset.p) : sel.delete(i.dataset.p); btn(); }));
    btn();
  };
  const btn = () => { $('.all', el).innerHTML = `${icon('trash')}${sel.size ? `Remove ${num(sel.size)} selected` : `Remove all ${num(rows.length)}`}`; $('.all', el).disabled = !rows.length; };
  const load = () => api('/empty-folders').then((r) => { rows = r; sel.clear(); draw(); }).catch(fail);
  $('.all', el).onclick = async () => {
    const paths = sel.size ? [...sel] : rows.map((r) => r.path);
    if (!(await confirmBox('Remove empty folders', `Remove <b>${num(paths.length)}</b> empty folders? Folders that received files since the last scan are skipped automatically.`, 'Remove', true))) return;
    if (await runTask(api('/empty-folders/delete', { paths }))) load();
  };
  load();
}
