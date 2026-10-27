// Users overview: compare every NAS user and jump into working with one of them.
import { api, avatar, bytes, esc, fail, h, icon, num, on, setScope, state, userColor, userLabel } from '../core.js';

export function usersView(root) {
  const el = h(`<div class="view"><div class="page-head"><div class="grow"><h1>Users</h1>
    <p>Everyone's storage side by side. Pick a user to work only with their files.</p></div></div>
    <div class="card" style="margin-bottom:18px"><h3>Storage</h3><div class="stack-bar"></div><div class="legend-row"></div></div>
    <div class="grid g3 cards"><div class="card"><div class="spin"></div></div></div></div>`);
  root.append(el);
  const load = async () => {
    let rows;
    try { rows = await api('/users/overview'); } catch (e) { return fail(e); }
    const total = rows.reduce((a, r) => a + r.size, 0) || 1;
    el.querySelector('.stack-bar').innerHTML = `<div style="display:flex;height:22px;border-radius:12px;overflow:hidden;background:var(--panel3)">
      ${rows.map((r) => `<div title="${esc(userLabel(r.name))}: ${bytes(r.size)}" style="width:${(100 * r.size) / total}%;background:${userColor(r.name)}"></div>`).join('')}</div>`;
    el.querySelector('.legend-row').innerHTML = `<div class="row wrap" style="gap:14px;margin-top:12px">${rows.map((r) => `<span class="row" style="gap:6px">${avatar(r.name)}<b>${esc(userLabel(r.name))}</b><span class="muted">${bytes(r.size)} · ${((100 * r.size) / total).toFixed(0)}%</span></span>`).join('')}</div>`;
    const box = el.querySelector('.cards');
    box.innerHTML = '';
    for (const r of rows) {
      const parts = [['Photos', r.photos[1], '#007aff'], ['Videos', r.videos[1], '#ff2d55'], ['Documents', r.docs[1], '#34c759'], ['Other', r.other, '#c7c7cc']];
      const sum = parts.reduce((a, p) => a + p[1], 0) || 1;
      const card = h(`<div class="card hover" style="display:flex;flex-direction:column;gap:12px">
        <div class="row">${avatar(r.name, 'lg')}<div class="grow" style="min-width:0"><div style="font-weight:700;font-size:16px" class="ellipsis">${esc(userLabel(r.name))}</div>
          <div class="muted" style="font-size:12.5px">${num(r.count)} files · ${bytes(r.size)}</div></div>
          ${state.scope?.length === 1 && state.scope[0] === r.name ? '<span class="badge accent">selected</span>' : ''}</div>
        <div style="display:flex;height:8px;border-radius:9px;overflow:hidden;background:var(--panel3)">${parts.map(([, v, c]) => `<div style="width:${(100 * v) / sum}%;background:${c}"></div>`).join('')}</div>
        <div class="kv" style="grid-template-columns:1fr auto">
          <div>Photos</div><div>${num(r.photos[0])} · ${bytes(r.photos[1])}</div>
          <div>Videos</div><div>${num(r.videos[0])} · ${bytes(r.videos[1])}</div>
          <div>Chat images</div><div>${num(r.kinds.chat[0])}</div>
          <div>Screenshots</div><div>${num(r.kinds.screenshot[0])}</div>
          <div>Duplicate copies</div><div>${num(r.dupes.extra)} · ${bytes(r.dupes.wasted)}</div>
          <div>Phone leftovers</div><div>${bytes(r.kinds.phonetrash[1] + r.kinds.cache[1])}</div>
        </div>
        <div class="row" style="margin-top:auto"><div class="grow"><div class="muted" style="font-size:12px">Safe to reclaim</div><b style="font-size:20px;letter-spacing:-.02em">${bytes(r.safe_reclaim)}</b></div>
          <button class="btn sm work">Work with</button><button class="btn sm primary clean">Clean up</button></div></div>`);
      card.querySelector('.work').onclick = () => { setScope([r.name]); location.hash = '#/dashboard'; };
      card.querySelector('.clean').onclick = () => { setScope([r.name]); location.hash = '#/quickclean'; };
      box.append(card);
    }
  };
  load();
  return on('changed', load);
}
