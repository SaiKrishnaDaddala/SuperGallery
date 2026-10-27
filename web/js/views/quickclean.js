// Cleanup candidates require an explicit selection and confirmation.
import { api, bytes, confirmBox, esc, fail, h, icon, num, on, runTask } from '../core.js';
import { scopeBanner } from './categories.js';

const QC_COLOR = { phonetrash: '#ff9500', cache: '#8e8e93', dupes: '#ff3b30', junk: '#8e8e93', temp: '#ffcc00', empty: '#c7c7cc' };
const LINK = { phonetrash: '#/categories/phonetrash', cache: '#/categories/cache', dupes: '#/duplicates', junk: '#/cleanup/junk', temp: '#/cleanup/temp', empty: '#/cleanup/empty' };

export function quickcleanView(root) {
  const picked = new Set();
  const el = h(`<div class="view review-view"><div class="page-head"><div class="grow"><h1>Review</h1>
    <p>A little space, thoughtfully reclaimed. Review each category before selecting it.</p></div></div>
    ${scopeBanner()}
    <div class="card hero" style="margin-bottom:18px;display:flex;align-items:center;gap:20px;flex-wrap:wrap">
      <div class="ring" style="width:120px;height:120px;flex:none"></div>
      <div class="grow"><div class="muted">Selected for review · categories may overlap</div><div class="total" style="font:700 44px/1.1 var(--font-display);letter-spacing:-.03em">…</div>
        <div class="muted cnt"></div></div>
      <button class="btn primary go" disabled style="height:44px;padding:0 26px;font-size:15px;border-radius:12px">Review selection</button></div>
    <div class="card" style="padding:6px 18px"><div class="items"></div></div></div>`);
  root.append(el);
  let data = [];
  const draw = () => {
    const sel = data.filter((d) => picked.has(d.key));
    const size = sel.reduce((a, d) => a + d.size, 0), count = sel.reduce((a, d) => a + d.count, 0);
    const all = data.reduce((a, d) => a + d.size, 0) || 1;
    el.querySelector('.total').textContent = bytes(size);
    el.querySelector('.cnt').textContent = `${num(count)} items selected`;
    el.querySelector('.go').disabled = !count;
    const pct = Math.min(1, size / all);
    el.querySelector('.ring').innerHTML = `<svg viewBox="0 0 120 120" width="120" height="120"><circle cx="60" cy="60" r="50" fill="none" stroke="var(--fill)" stroke-width="14"/>
      <circle cx="60" cy="60" r="50" fill="none" stroke="var(--ok)" stroke-width="14" stroke-linecap="round" stroke-dasharray="${314 * pct} 314" transform="rotate(-90 60 60)" style="transition:stroke-dasharray .6s var(--ease)"/>

      <text x="60" y="66" text-anchor="middle" style="font-size:20px;font-weight:700;fill:var(--text)">${Math.round(pct * 100)}%</text></svg>`;
    const box = el.querySelector('.items');
    box.innerHTML = '';
    for (const d of data) {
      const row = h(`<div class="insight${d.count ? '' : ' is-empty'}">
        <label class="switch"><input type="checkbox" aria-label="Select ${esc(d.title)}" ${picked.has(d.key) && d.count ? 'checked' : ''} ${d.count ? '' : 'disabled'}><span></span></label>
        <div class="ic" style="background:${QC_COLOR[d.key] || '#007aff'}">${icon(d.icon)}</div><div class="grow"><div class="t">${esc(d.title)}</div><div class="d">${esc(d.desc)} · ${num(d.count)} items</div></div>
        <div class="s">${bytes(d.size)}</div><a class="btn sm ghost" href="${LINK[d.key]}">Review</a></div>`);
      row.querySelector('input').onchange = (e) => { const label = e.target.getAttribute('aria-label'); e.target.checked ? picked.add(d.key) : picked.delete(d.key); draw(); [...box.querySelectorAll('input')].find(input => input.getAttribute('aria-label') === label)?.focus(); };
      box.append(row);
    }
  };
  const load = async () => {
    try { data = (await api('/quickclean')).sort((a,b) => b.size - a.size || b.count - a.count); } catch (e) { return fail(e); }
    draw();
  };
  el.querySelector('.go').onclick = async () => {
    const sel = data.filter((d) => picked.has(d.key) && d.count);
    const size = sel.reduce((a, d) => a + d.size, 0), count = sel.reduce((a, d) => a + d.count, 0);
    if (!(await confirmBox('Review cleanup', `Move <b>${num(count)}</b> items (<b>${bytes(size)}</b>) to the recycle bin?<br><br>${sel.map((d) => `• ${esc(d.title)}`).join('<br>')}<br><br><span class="muted">Duplicates keep the oldest copy for each user. Files remain recoverable until the configured recycle-bin retention expires.</span>`, 'Clean now'))) return;
    const t = await runTask(api('/quickclean/run', { keys: sel.map((d) => d.key) }));
    if (t) load();
  };
  load();
  return on('changed', load);
}
