// Recycle bin: everything deleted from the app, restorable until the retention period ends.
import { $, $$, api, bytes, confirmBox, date, debounce, esc, fail, h, icon, num, runTask, shortPath } from '../core.js';

export function trashView(root) {
  const st = { items: [], total: 0, size: 0, sel: new Set(), q: '' };
  const el = h(`<div class="view"><div class="page-head"><div class="grow"><h1>Recycle bin</h1><p class="sum"></p></div>
    <button class="btn rs">${icon('restore')}Restore all</button><button class="btn danger em">${icon('trash')}Empty recycle bin</button></div>
    <div class="selbar hidden"></div>
    <div class="filters"><input class="input sm q" placeholder="Search deleted files…" style="width:260px"></div>
    <div class="card" style="padding:0;overflow:auto;max-height:calc(100vh - 260px)"><table class="tbl"><thead><tr><th style="width:34px"><input type="checkbox" class="all"></th>
      <th></th><th>Name</th><th>Original location</th><th class="r">Size</th><th>Deleted</th><th>Reason</th></tr></thead><tbody></tbody></table></div></div>`);
  root.append(el);

  async function load() {
    try {
      const r = await api(`/trash?limit=2000&q=${encodeURIComponent(st.q)}`);
      Object.assign(st, { items: r.items, total: r.total, size: r.total_size });
      $('.sum', el).innerHTML = `${num(r.total)} items · ${bytes(r.total_size)} · items are erased automatically after ${r.retention_days} days`;
      draw();
    } catch (e) { fail(e); }
  }
  function draw() {
    const now = Date.now() / 1000;
    $('tbody', el).innerHTML = st.items.length ? st.items.map((t) => `<tr class="${st.sel.has(t.id) ? 'sel' : ''}" data-id="${t.id}"><td><input type="checkbox" ${st.sel.has(t.id) ? 'checked' : ''}></td>
      <td style="width:46px"><img src="/api/trash/thumb/${t.id}" loading="lazy" style="width:34px;height:34px;object-fit:cover;border-radius:6px;display:block" onerror="this.style.visibility='hidden'"></td>
      <td class="ellipsis" style="max-width:280px">${esc(t.orig_path.split('/').pop())}</td><td class="mono muted ellipsis" style="max-width:380px">${esc(shortPath(t.orig_path.split('/').slice(0, -1).join('/')))}</td>
      <td class="r num">${bytes(t.size)}</td><td class="muted num" title="${date(t.deleted_at, true)}">${Math.floor((now - t.deleted_at) / 86400) ? Math.floor((now - t.deleted_at) / 86400) + ' days ago' : 'today'}</td><td class="muted">${esc(t.reason || '')}</td></tr>`).join('')
      : `<tr><td colspan="7"><div class="empty">${icon('trash')}<div>Recycle bin is empty</div></div></td></tr>`;
    $$('tbody tr[data-id]', el).forEach((tr) => (tr.onclick = () => { const id = +tr.dataset.id; st.sel.has(id) ? st.sel.delete(id) : st.sel.add(id); draw(); }));
    $('.all', el).checked = st.items.length && st.items.every((t) => st.sel.has(t.id));
    const sb = $('.selbar', el);
    sb.classList.toggle('hidden', !st.sel.size);
    if (st.sel.size) {
      const size = st.items.filter((t) => st.sel.has(t.id)).reduce((a, t) => a + t.size, 0);
      sb.innerHTML = `<span class="count">${num(st.sel.size)} selected</span><span class="muted">· ${bytes(size)}</span><span class="grow"></span>
        <button class="btn primary r1">${icon('restore')}Restore</button><button class="btn danger d1">${icon('trash')}Delete forever</button>`;
      $('.r1', sb).onclick = async () => { if (await runTask(api('/trash/restore', { ids: [...st.sel] }))) { st.sel.clear(); load(); } };
      $('.d1', sb).onclick = async () => {
        if (!(await confirmBox('Delete forever?', `Permanently erase <b>${num(st.sel.size)}</b> items? This cannot be undone.`, 'Erase', true))) return;
        if (await runTask(api('/trash/empty', { ids: [...st.sel] }))) { st.sel.clear(); load(); }
      };
    }
  }
  $('.all', el).onchange = (e) => { st.items.forEach((t) => (e.target.checked ? st.sel.add(t.id) : st.sel.delete(t.id))); draw(); };
  $('.q', el).oninput = debounce((e) => { st.q = e.target.value; load(); }, 250);
  $('.rs', el).onclick = async () => {
    if (!st.total || !(await confirmBox('Restore everything?', `Put all <b>${num(st.total)}</b> items back where they were?`, 'Restore all'))) return;
    if (await runTask(api('/trash/restore', {}))) load();
  };
  $('.em', el).onclick = async () => {
    if (!st.total || !(await confirmBox('Empty recycle bin?', `Permanently erase <b>${num(st.total)}</b> items and free <b>${bytes(st.size)}</b>? This cannot be undone.`, 'Empty recycle bin', true))) return;
    if (await runTask(api('/trash/empty', {}))) load();
  };
  load();
}
