// Duplicate folders: whole folders copied more than once (e.g. the same phone backup twice).
import { $, $$, api, avatar, bytes, confirmBox, esc, fail, h, icon, num, on, runTask, shortPath, toast } from '../core.js';
import { scopeBanner } from './categories.js';

export function dupfoldersView(root) {
  const st = { perUser: localStorage.getItem('df-across') !== '1', sel: new Set(), groups: [], shown: 40 };
  const el = h(`<div class="view"><div class="page-head"><div class="grow"><h1>Duplicate folders</h1>
    <p class="sum">Folders whose files are exact copies of another folder — remove a whole copy at once.</p></div>
    <span class="row" style="gap:10px"><span class="muted">Within each user</span><label class="switch"><input type="checkbox" class="peruser" aria-label="Within each user"><span></span></label></span></div>
    ${scopeBanner()}<div class="selbar hidden"></div><div class="groups"></div><div class="more" style="text-align:center"></div></div>`);
  root.append(el);
  const selbar = () => {
    const sb = $('.selbar', el);
    const sel = st.groups.flatMap((g) => g.folders).filter((f) => st.sel.has(f.path));
    sb.classList.toggle('hidden', !sel.length);
    if (!sel.length) return;
    const size = sel.reduce((a, f) => a + f.size, 0);
    sb.innerHTML = `${icon('folder')}<span class="count">${num(sel.length)} folder copies</span><span class="muted">· frees ${bytes(size)}</span><span class="grow"></span>
      <button class="btn sm ghost clr">Clear</button><button class="btn danger go">${icon('trash')}Remove ${num(sel.length)} copies</button>`;
    $('.clr', sb).onclick = () => { st.sel.clear(); draw(); };
    $('.go', sb).onclick = async () => {
      if (!(await confirmBox('Remove duplicate folders', `Move <b>${num(sel.length)}</b> folder copies (${bytes(size)}) to the recycle bin? One copy of every folder is always kept.`, 'Remove', true))) return;
      if (await runTask(api('/dupfolders/delete', { paths: sel.map((f) => f.path), per_user: st.perUser }))) { st.sel.clear(); load(); }
    };
  };
  const draw = () => {
    const box = $('.groups', el);
    box.innerHTML = st.groups.length ? '' : `<div class="empty">${icon('check')}<div>No duplicate folders found</div></div>`;
    for (const g of st.groups.slice(0, st.shown)) {
      const ge = h(`<div class="group"><div class="group-head">${icon('folder')}<div class="grow"><b>${num(g.count)} files · ${bytes(g.size)}</b>
        <div class="muted" style="font-size:12.5px">${g.folders.length} identical copies · <span class="danger-text">${bytes(g.reclaim)} reclaimable</span></div></div>
        <button class="btn sm ghost kf">Keep first only</button></div>
        ${g.folders.map((f, i) => `<div class="gfile ${st.sel.has(f.path) ? 'del' : ''}" data-p="${esc(f.path)}"><input type="checkbox" ${st.sel.has(f.path) ? 'checked' : ''} aria-label="Select ${esc(f.path)}">
          <div class="p ellipsis mono row" style="gap:6px">${avatar(f.owner)}<span class="ellipsis">${esc(shortPath(f.path))}</span></div>
          <span class="muted">${i === 0 ? 'shortest path' : ''}</span><span>${st.sel.has(f.path) ? '<span class="badge danger">remove</span>' : '<span class="badge ok">keep</span>'}</span>
          <a class="btn sm ghost icon" href="#/files?path=${encodeURIComponent(f.path)}" title="Open">${icon('folderOpen')}</a></div>`).join('')}</div>`);
      $$('.gfile', ge).forEach((r) => (r.onclick = (e) => {
        if (e.target.closest('a')) return;
        const p = r.dataset.p;
        if (st.sel.has(p)) st.sel.delete(p);
        else if (g.folders.every((f) => f.path === p || st.sel.has(f.path))) return toast('Keep at least one copy', 'info');
        else st.sel.add(p);
        draw();
      }));
      $('.kf', ge).onclick = () => { g.folders.forEach((f, i) => (i ? st.sel.add(f.path) : st.sel.delete(f.path))); draw(); };
      box.append(ge);
    }
    const more = $('.more', el);
    more.innerHTML = st.groups.length > st.shown ? `<button class="btn">Show more (${num(st.groups.length - st.shown)} left)</button>` : '';
    if (more.firstElementChild) more.firstElementChild.onclick = () => { st.shown += 40; draw(); };
    selbar();
  };
  const load = async () => {
    $('.groups', el).innerHTML = '<div class="empty"><div class="spin" style="margin:auto"></div></div>';
    try { st.groups = await api('/dupfolders?per_user=' + st.perUser); } catch (e) { return fail(e); }
    const total = st.groups.reduce((a, g) => a + g.reclaim, 0);
    $('.sum', el).innerHTML = st.groups.length ? `<b style="color:var(--text)">${num(st.groups.length)}</b> folders exist more than once · <b class="danger-text">${bytes(total)}</b> reclaimable` : 'Folders whose files are exact copies of another folder.';
    draw();
  };
  $('.peruser', el).checked = st.perUser;
  $('.peruser', el).onchange = (e) => { st.perUser = e.target.checked; localStorage.setItem('df-across', st.perUser ? '0' : '1'); st.sel.clear(); load(); };
  load();
  return on('changed', load);
}
