// New-version notice, release notes and how to update. The server only reads the public GitHub release.
import { $, api, date, esc, fail, h, icon, modal, toast } from './core.js';

const DISMISS_KEY = 'sg-update-dismissed';
const read = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };

// Release notes are plain Markdown; render a safe subset (escaped text, headings, lists, bold, code).
function notesHtml(md) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  const out = []; let list = false;
  for (const line of (md || 'No release notes were published.').split(/\r?\n/)) {
    const item = line.match(/^\s*[-*]\s+(.*)/), head = line.match(/^#{1,4}\s+(.*)/);
    if (item) { if (!list) { out.push('<ul>'); list = true; } out.push(`<li>${inline(item[1])}</li>`); continue; }
    if (list) { out.push('</ul>'); list = false; }
    if (head) out.push(`<h3>${inline(head[1])}</h3>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  if (list) out.push('</ul>');
  return out.join('');
}

export async function showNotes(info) {
  await modal({ title: `What's new in SuperGallery ${info.latest}`, icon: 'sparkles', wide: true,
    body: h(`<div class="release-notes">${info.published ? `<p class="muted">Released ${esc(date(Date.parse(info.published) / 1000))} · you have ${esc(info.current)}</p>` : ''}${notesHtml(info.notes)}</div>`),
    actions: [{ label: 'Close', value: null }, { label: 'How to update', cls: 'primary', value: 'update' }] }) === 'update' && startUpdate(info);
}

export async function startUpdate(info) {
  if (info.one_click) {
    const go = await modal({ title: `Update to ${info.latest}?`, icon: 'download',
      body: h('<div class="col"><p>Watchtower will download the new version and restart SuperGallery. Your library, people, albums and settings stay as they are.</p><p class="muted">The app is unavailable for about a minute; this page reconnects by itself.</p></div>'),
      actions: [{ label: 'Not now', value: null }, { label: 'Update now', cls: 'primary', value: 'go' }] });
    if (go !== 'go') return;
    try { await api('/updates/apply', {}); } catch (e) { return fail(e); }
    toast('Updating… SuperGallery will be back in a minute.', 'info');
    const started = Date.now();
    const wait = async () => {
      try { const f = await api('/features'); if (f.version === info.latest) return location.reload(); } catch { /* restarting */ }
      if (Date.now() - started < 10 * 60 * 1000) setTimeout(wait, 5000);
    };
    setTimeout(wait, 8000);
    return;
  }
  await modal({ title: `Update to ${info.latest}`, icon: 'download', wide: true,
    body: h(`<div class="col update-steps">
      <p>Your library, people, albums and settings are kept; only the app is replaced.</p>
      <h3>UGREEN NAS (UGOS)</h3><ol><li>Open <b>Docker → Project → supergallery</b>.</li><li>Choose <b>Redeploy</b>, tick <b>Pull the latest image</b>, then <b>Deploy</b>.</li></ol>
      <h3>Docker Compose</h3><pre><code>docker compose pull && docker compose up -d</code></pre>
      <p class="muted">Want a one-click Update button? Add the optional Watchtower container described in the README (“One-click updates”).</p></div>`),
    actions: [{ label: 'Done', cls: 'primary' }] });
}

// Floating notice after sign-in, once per version unless the user asks again from Settings.
export async function notifyIfUpdate() {
  let info;
  try { info = await api('/updates'); } catch { return; }
  if (!info.available || read(DISMISS_KEY) === info.latest || document.querySelector('.update-notice')) return;
  const box = h(`<aside class="update-notice" role="status"><div class="update-icon">${icon('sparkles')}</div>
    <div class="grow"><b>SuperGallery ${esc(info.latest)} is available</b><span>You have ${esc(info.current)}</span></div>
    <button class="btn sm notes">What's new</button><button class="btn sm primary update">Update</button>
    <button class="btn sm ghost icon later" aria-label="Remind me later">${icon('x')}</button></aside>`);
  document.body.append(box);
  $('.notes', box).onclick = () => showNotes(info);
  $('.update', box).onclick = () => startUpdate(info);
  $('.later', box).onclick = () => { write(DISMISS_KEY, info.latest); box.remove(); };
}

// Settings card: current version, latest release, automatic checks.
export function updatesCard(host) {
  let alive = true;
  async function draw(force = false) {
    let info;
    try { info = force ? await api('/updates/check', {}) : await api('/updates'); } catch (e) { return fail(e); }
    if (!alive) return;
    const status = !info.enabled ? 'Automatic checks are off.'
      : info.error ? info.error
      : info.available ? `<b>${esc(info.latest)}</b> is available.`
      : info.latest ? `You're up to date (latest release ${esc(info.latest)}).` : 'Not checked yet.';
    host.innerHTML = `<section class="card updates-card"><h3>${icon('download')}Updates</h3>
      <p>Version <b>${esc(info.current)}</b> · ${status}${info.checked ? ` <span class="muted">Checked ${esc(date(info.checked))}.</span>` : ''}</p>
      <div class="row wrap" style="gap:8px">${info.available ? '<button class="btn primary u-update">Update</button><button class="btn u-notes">What\'s new</button>' : ''}<button class="btn u-check">${icon('refresh')}Check now</button>${info.latest && !info.available ? '<button class="btn ghost u-notes">Release notes</button>' : ''}</div>
      <label class="row" style="gap:10px;margin-top:14px"><span class="switch"><input type="checkbox" class="u-auto" ${info.enabled ? 'checked' : ''}><span></span></span><span>Check GitHub for new versions twice a day. Only the public release page is read; nothing about your library is sent.</span></label></section>`;
    $('.u-check', host).onclick = async (e) => { e.target.disabled = true; await draw(true); };
    host.querySelectorAll('.u-notes').forEach((b) => (b.onclick = () => showNotes(info)));
    $('.u-update', host)?.addEventListener('click', () => startUpdate(info));
    $('.u-auto', host).onchange = async (e) => { try { await api('/updates', { enabled: e.target.checked }, 'PUT'); draw(); } catch (err) { fail(err); } };
  }
  draw();
  return () => { alive = false; };
}
