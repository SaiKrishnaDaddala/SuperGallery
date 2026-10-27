// Similar photos: look-alike groups, keep the best one per group (largest / sharpest…), delete the rest.
import { $, $$, api, ago, avatar, bytes, confirmDelete, esc, fail, h, icon, num, on, ownerChip, runTask, shortPath, thumbUrl, toast } from '../core.js';
import { scopeBanner } from './categories.js';
import { lightbox } from '../lightbox.js';

const KEEP = [['largest', 'Keep highest resolution'], ['sharpest', 'Keep sharpest'], ['newest', 'Keep newest'], ['oldest', 'Keep oldest'], ['shortest_path', 'Keep shortest path']];
const LEVELS = [[5, 'Strict'], [10, 'Normal'], [16, 'Loose'], [22, 'Very loose']];

export function similarView(root) {
  const st = { offset: 0, sel: new Map(), keep: 'largest', total: 0, perUser: localStorage.getItem('sim-across') !== '1' };
  const el = h(`<div class="view">
    <div class="page-head"><div class="grow"><h1>Similar photos</h1><p class="sum">Resized copies, re-saved JPEGs, edits and burst shots.</p></div></div>
    ${scopeBanner()}
    <div class="card" style="margin-bottom:14px"><h3>${icon('wand')}Keep the best, remove the rest<span class="right row" style="gap:10px;font-size:13px"><span class="muted">Within each user</span>
      <label class="switch"><input type="checkbox" class="peruser" aria-label="Within each user"><span></span></label></span></h3>
      <div class="row wrap" style="gap:10px">
        <select class="input keep" aria-label="Which photo to keep">${KEEP.map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select>
        <button class="btn primary auto">${icon('wand')}Auto-select all groups</button>
        <span class="muted" style="margin-left:14px">Match</span><div class="seg lvl">${LEVELS.map(([v, l]) => `<button data-v="${v}">${l}</button>`).join('')}</div>
        <span class="grow"></span><button class="btn ghost clear">${icon('x')}Clear</button>
      </div>
      <div class="faint" style="font-size:12.5px;margin-top:10px">"Keep highest resolution" marks every smaller / lower-quality version for deletion — perfect for WhatsApp copies and thumbnails. Click any photo to toggle, double-click to view.</div></div>
    <div class="selbar hidden"></div>
    <div class="groups"></div><div class="more-slot" style="text-align:center;padding:10px"></div></div>`);
  root.append(el);

  const total = () => [...st.sel.values()].reduce((a, x) => a + x.size, 0);
  function selbar() {
    const sb = $('.selbar', el);
    sb.classList.toggle('hidden', !st.sel.size);
    if (!st.sel.size) return;
    sb.innerHTML = `${icon('trash')}<span class="count">${num(st.sel.size)} photos marked</span><span class="muted">· frees ${bytes(total())}</span><span class="grow"></span>
      <button class="btn ghost sm clr">Clear</button><button class="btn danger go">${icon('trash')}Delete ${num(st.sel.size)} photos</button>`;
    $('.clr', sb).onclick = () => { st.sel.clear(); paint(); };
    $('.go', sb).onclick = async () => {
      const t = await confirmDelete({ ids: [...st.sel.keys()], count: st.sel.size, size: total(), guard: st.perUser ? 'similar' : 'similar_all', reason: 'similar photos' });
      if (t?.status === 'done') { st.sel.clear(); reload(); }
    };
  }
  function paint() {
    $$('.sim-card', el).forEach((c) => {
      const del = st.sel.has(+c.dataset.id);
      c.classList.toggle('del', del);
      c.classList.toggle('keep', !del);
      $('.tag', c).textContent = del ? 'DELETE' : 'KEEP';
    });
    selbar();
  }
  function groupEl(g) {
    const best = g.files[0];
    const e = h(`<div class="group"><div class="group-head">${g.owner ? ownerChip(g.owner) : ''}<b>${num(g.files.length)} similar photos</b><span class="muted">· up to ${bytes(g.reclaim)} reclaimable</span>
      <span class="grow"></span><button class="btn sm ghost kb">Keep best only</button><button class="btn sm ghost ka">Keep all</button></div>
      <div class="sim-row" tabindex="0" role="group" aria-label="Similar photos, scroll sideways for more">${g.files.map((f) => `<div class="sim-card" data-id="${f.id}"><img loading="lazy" alt="${esc(f.name)}" src="${thumbUrl(f, 256)}">
        <span class="tag"></span>${f.id === best.id ? '<span class="best">★ best</span>' : ''}
        <div class="info"><div class="ellipsis" title="${esc(f.path)}" style="font-weight:600">${esc(f.name)}</div>
        <div class="muted">${f.width}×${f.height} · ${bytes(f.size)}</div>
        <div class="faint ellipsis mono row" style="font-size:11px;gap:5px">${g.owner ? '' : avatar(f.owner)}<span class="ellipsis">${esc(shortPath(f.dir))}</span></div>
        ${f.blur != null && f.blur < 40 ? '<span class="badge warn" style="margin-top:4px">blurry</span>' : ''}</div></div>`).join('')}</div></div>`);
    $$('.sim-card', e).forEach((c) => {
      const f = g.files.find((x) => x.id === +c.dataset.id);
      c.onclick = () => {
        if (st.sel.has(f.id)) st.sel.delete(f.id);
        else {
          if (g.files.every((x) => x.id === f.id || st.sel.has(x.id))) return toast('Keep at least one photo of each group', 'info');
          st.sel.set(f.id, f);
        }
        paint();
      };
      c.ondblclick = () => lightbox(g.files, g.files.indexOf(f));
    });
    $('.kb', e).onclick = () => { g.files.forEach((x) => (x.id === best.id ? st.sel.delete(x.id) : st.sel.set(x.id, x))); paint(); };
    $('.ka', e).onclick = () => { g.files.forEach((x) => st.sel.delete(x.id)); paint(); };
    return e;
  }
  async function page() {
    const box = $('.more-slot', el);
    box.innerHTML = '<div class="spin" style="margin:auto"></div>';
    try {
      const r = await api('/similar', { limit: 30, offset: st.offset, per_user: st.perUser });
      st.total = r.groups;
      $$('.lvl button', el).forEach((b) => b.classList.toggle('on', +b.dataset.v === r.threshold));
      $('.sum', el).innerHTML = r.groups ? `<b style="color:var(--text)">${num(r.groups)}</b> groups · ${num(r.photos)} photos · up to <b class="danger-text">${bytes(r.reclaim)}</b> reclaimable <span class="faint">· grouped ${ago(r.computed_at)}</span>`
        : 'No look-alike photos found yet. Photos are analyzed after each scan.';
      if (!r.groups) $('.groups', el).innerHTML = `<div class="empty">${icon('images')}<div>No similar photos</div></div>`;
      r.items.forEach((g) => $('.groups', el).append(groupEl(g)));
      st.offset += r.items.length;
      paint();
      box.innerHTML = st.offset < r.groups ? `<button class="btn">Load more (${num(r.groups - st.offset)} groups left)</button>` : '';
      if (box.firstElementChild) box.firstElementChild.onclick = page;
    } catch (e) { fail(e); box.innerHTML = ''; }
  }
  function reload() { st.offset = 0; $('.groups', el).innerHTML = ''; page(); }

  $('.peruser', el).checked = st.perUser;
  $('.peruser', el).onchange = (e) => { st.perUser = e.target.checked; localStorage.setItem('sim-across', st.perUser ? '0' : '1'); st.sel.clear(); reload(); };
  $('.keep', el).onchange = (e) => (st.keep = e.target.value);
  $('.auto', el).onclick = async () => {
    try {
      const r = await api('/similar/autoselect', { keep: st.keep, per_user: st.perUser });
      st.sel.clear();
      for (const [id, size] of r.items) st.sel.set(id, { id, size });
      paint();
      toast(`Marked <b>${num(r.items.length)}</b> photos in ${num(r.groups)} groups · ${bytes(r.size)}`);
    } catch (e) { fail(e); }
  };
  $('.clear', el).onclick = () => { st.sel.clear(); paint(); };
  $$('.lvl button', el).forEach((b) => (b.onclick = async () => {
    const t = await runTask(api('/scan', { mode: 'similar', threshold: +b.dataset.v }));
    if (t) { st.sel.clear(); reload(); }
  }));
  page();
  return on('indexed', reload);
}
