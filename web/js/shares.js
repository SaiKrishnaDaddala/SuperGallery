// Share links: make a link for chosen photos, and list or turn off existing links in Settings.
import { $, $$, api, date, esc, fail, h, icon, modal, num, toast } from './core.js';

async function copy(text, input) {
  try { await navigator.clipboard.writeText(text); return true; } catch {
    input?.select();
    try { return document.execCommand('copy'); } catch { return false; }
  }
}

/** ids: file ids (photos and videos); title: suggested link name. */
export async function shareDialog(ids, title = '') {
  if (!ids.length) return;
  const body = h(`<div class="col share-form">
    <label class="field"><span>Name</span><input class="input share-title" maxlength="80" placeholder="Shared photos"></label>
    <label class="field"><span>Link works for</span><select class="input share-days"><option value="1">1 day</option><option value="7" selected>1 week</option><option value="30">30 days</option></select></label>
    <p class="muted">Anyone with the link can view and download these ${num(ids.length)} ${ids.length === 1 ? 'item' : 'items'} — and nothing else — until it expires. Turn it off any time in Settings → Shared links. Only photos and videos are shared.</p></div>`);
  $('.share-title', body).value = title;
  const choice = await modal({ title: 'Create a share link', body, icon: 'upload',
    actions: [{ label: 'Cancel', value: null }, { label: 'Create link', cls: 'primary', value: (bg) => ({ title: $('.share-title', bg).value, days: +$('.share-days', bg).value }) }] });
  if (!choice) return;
  let s;
  try { s = await api('/shares', { ids, title: choice.title, days: choice.days }); } catch (e) { return fail(e); }
  const url = location.origin + s.path;
  const done = h(`<div class="col"><p>Link for <b>${num(s.count)}</b> ${s.count === 1 ? 'item' : 'items'}, working until <b>${esc(date(s.expires))}</b>.</p>
    <input class="input share-link" readonly aria-label="Share link">
    <p class="muted">Copy it now. For your privacy the NAS keeps only a fingerprint of the link, so it cannot show it again.</p></div>`);
  $('.share-link', done).value = url;
  await modal({ title: 'Your link is ready', body: done, icon: 'check', onOpen: (bg) => $('.share-link', bg).select(),
    actions: [{ label: 'Done', value: null }, { label: 'Copy link', cls: 'primary', validate: async (bg) => {
      toast((await copy(url, $('.share-link', bg))) ? 'Link copied' : 'Select the link and copy it', 'ok');
      return false;
    } }] });
}

export function sharesCard(host) {
  let alive = true;
  const el = h(`<section class="card shares-card"><h2>${icon('upload')}Shared links</h2><div class="share-list"><p class="muted">Loading…</p></div></section>`);
  host.append(el);
  async function load() {
    let r;
    try { r = await api('/shares'); } catch (e) { $('.share-list', el).innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
    if (!alive) return;
    const list = $('.share-list', el);
    list.innerHTML = r.shares.length ? r.shares.map((s) => `<div class="share-row${s.active ? '' : ' off'}"><div class="grow"><b>${esc(s.title)}</b>
      <div class="muted small">${num(s.count)} ${s.count === 1 ? 'item' : 'items'} · ${s.active ? `until ${esc(date(s.expires))}` : 'turned off or expired'} · opened ${num(s.views)} ${s.views === 1 ? 'time' : 'times'}</div></div>
      ${s.active ? `<button class="btn sm danger revoke" data-id="${s.id}">Turn off</button>` : ''}</div>`).join('')
      : '<p class="muted">No links yet. Select photos anywhere and choose Share link.</p>';
    $$('.revoke', list).forEach((b) => (b.onclick = async () => {
      try { await api(`/shares/${b.dataset.id}/revoke`, {}); toast('Link turned off'); load(); } catch (e) { fail(e); }
    }));
  }
  load();
  return () => { alive = false; };
}
