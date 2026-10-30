// Index status, scan controls, configuration and keyboard shortcuts.
import { $, $$, ago, api, bytes, emit, esc, fail, h, icon, modal, num, on, poll, state, toast } from '../core.js';
import { securityCard } from '../security.js';
import { libraryCare } from '../backup-card.js';
import { featureCard } from '../features.js';
import { networkCard } from '../network.js';
import { updatesCard } from '../updates.js';

const KEYS = [
  ['↑ ↓ / Home / End / PgUp / PgDn', 'Move focus (Shift = extend selection)'], ['Enter', 'Open folder / file'], ['Backspace', 'Parent folder'],
  ['Space', 'Quick preview'], ['Ctrl+A / Ctrl+I', 'Select all / invert'], ['Ctrl+C / Ctrl+X / Ctrl+V', 'Copy / cut / paste'],
  ['Del / Shift+Del', 'Recycle / delete'], ['F2', 'Rename (bulk rename for several)'], ['F7', 'New folder'],
  ['Tab', 'Switch pane (dual pane)'], ['F5 / F6', 'Copy / move to other pane'], ['Ctrl+F', 'Filter current folder'],
  ['Alt+← / Alt+→', 'Back / forward'], ['/', 'Focus global smart search'], ['Type letters', 'Jump to file by name'],
];

export function settingsView(root) {
  const el = h(`<div class="view settings-view"><div class="page-head"><div class="grow"><h1>Settings</h1><p>Appearance, storage, and your library.</p></div>
    <button class="btn primary scan">${icon('refresh')}Rescan now</button></div><div class="security-host"></div><div class="grid g2 body"></div></div>`);
  root.append(el);
  const stopSecurity=securityCard($('.security-host',el));
  const networkHost=document.createElement('div');networkHost.className='features-host';$('.security-host',el).after(networkHost);const stopNetwork=networkCard(networkHost);
  const featuresHost=document.createElement('div');featuresHost.className='features-host';$('.security-host',el).after(featuresHost);const stopFeatures=featureCard(featuresHost);
  const careHost=document.createElement('div');careHost.className='care-host';featuresHost.after(careHost);const stopCare=libraryCare(careHost);
  const updatesHost=document.createElement('div');updatesHost.className='features-host';featuresHost.after(updatesHost);const stopUpdates=updatesCard(updatesHost);
  $('.scan', el).onclick = () => api('/scan', {}).then(() => poll(true)).catch(fail);
  let signature = '';
  const showAppearance = () => {
    const theme = localStorage.getItem('theme') || 'system';
    $$('[data-appearance]',el).forEach(button => button.setAttribute('aria-pressed',String(button.dataset.appearance === theme)));
  };
  const draw = () => {
    const s = state.status;
    if (!s) return;
    const next = JSON.stringify([s.files,s.size,s.last_scan,s.scan_interval_hours,s.trash_count,s.trash_size,s.trash_days,s.ffmpeg,s.env_password,s.roots,!!window.__sgInstall]);
    if (next === signature) return;
    signature = next;
    const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    const embedded = window.self !== window.top;
    const installEvt = window.__sgInstall;
    $('.body', el).innerHTML = `
      <section class="card span2 appearance-card"><h3>${icon('sun')}Appearance</h3><p class="muted">Choose a look, or follow your device.</p><div class="appearance-options" role="group" aria-label="Appearance">${[['light','Light'],['dark','Dark'],['system','Automatic']].map(([key,label]) => `<button data-appearance="${key}" aria-pressed="false"><span class="appearance-preview preview-${key}" aria-hidden="true"><i></i><span><b></b><em></em><em></em></span></span><span>${label}</span>${icon('check')}</button>`).join('')}</div></section>
      <div class="card"><h3>${icon('scan')}Index</h3><div class="kv">
        <div>Files</div><div>${num(s.files)} · ${bytes(s.size)}</div><div>Last scan</div><div>${ago(s.last_scan)}</div>
        <div>Auto rescan</div><div>${s.scan_interval_hours ? `every ${s.scan_interval_hours} h` : 'off'}</div>
        <div>Recycle bin</div><div>${num(s.trash_count)} items · ${bytes(s.trash_size)} · kept ${s.trash_days} days</div>
        <div>Video thumbs</div><div>${s.ffmpeg ? '<span class="badge ok">ffmpeg available</span>' : '<span class="badge warn">ffmpeg missing</span>'}</div>
        <div>Password</div><div><span class="badge ok">enabled</span> ${s.env_password ? '<span class="faint">(set in docker-compose)</span>' : '<button class="btn sm chpw">Change</button>'}</div>
        <div>Volumes</div><div>${s.roots.map((r) => `<div class="mono">${esc(r)}</div>`).join('')}</div></div>
        <button class="btn sm logout" style="margin-top:14px">${icon('logout')}Sign out</button></div>
      <div class="card"><h3>${icon('info')}About your library</h3><div class="col" style="gap:8px;font-size:13.5px">
        <div>• <b>Scanning</b> stores names, sizes and dates in a local database so browsing and analytics do not need to reread every file. Performance depends on your library and NAS.</div>
        <div>• <b>Duplicates</b>: only files with the same size are read; a quick hash of start/middle/end narrows candidates, then a full BLAKE2 hash confirms exact copies.</div>
        <div>• <b>Similar photos</b>: each photo gets a 128-bit perceptual fingerprint; photos whose fingerprints are close (and share an aspect ratio) are grouped.</div>
        <div>• <b>Deleting</b> moves files to <span class="mono">.supergallery_trash</span> for recovery until its retention period expires. Keep an independent backup of originals.</div>
        <div>• Change settings with environment variables in <span class="mono">docker-compose.yml</span> (see README).</div></div></div>
      <div class="card span2"><h3>${icon('download')}Open SuperGallery as an app<span class="right">${embedded ? '<span class="badge ok">Embedded window</span>' : standalone ? '<span class="badge ok">App window</span>' : '<span class="badge">Browser</span>'}</span></h3>
        <div class="muted" style="margin:-6px 0 14px">This release runs as a web app. Native UGREEN package distribution requires vendor authorization and is not included in the public release. You can add the web app to your computer or phone below.</div>
        <div class="grid g3" style="gap:14px">
          <div class="insight" style="align-items:flex-start"><div class="ic">${icon('monitor')}</div><div><div class="t">Windows / Mac (Chrome or Edge)</div>
            <div class="d">Open <b>${esc(location.origin)}</b> → browser menu <b>⋮</b> → <b>Cast, save and share</b> → <b>Install page as app…</b> (Edge: <b>Apps → Install this site as an app</b>). If you only see <b>Create shortcut</b>, tick <b>Open as window</b>. It then lives in your Start menu and taskbar.</div></div></div>
          <div class="insight" style="align-items:flex-start"><div class="ic">${icon('image')}</div><div><div class="t">Android</div>
            <div class="d">Open the address in Chrome → menu <b>⋮</b> → <b>Add to Home screen</b> → <b>Install</b>. Opens full-screen with the SuperGallery icon.</div></div></div>
          <div class="insight" style="align-items:flex-start"><div class="ic">${icon('star')}</div><div><div class="t">iPhone / iPad</div>
            <div class="d">Open the address in Safari → <b>Share</b> → <b>Add to Home Screen</b>. It opens full-screen like a native app.</div></div></div>
        </div>
        ${installEvt ? `<button class="btn primary install" style="margin-top:14px">${icon('download')}Install now</button>` : ''}</div>
      <div class="card span2"><h3>${icon('zap')}Keyboard shortcuts (file manager)</h3><div class="grid g2" style="gap:6px 24px">
        ${KEYS.map(([k, d]) => `<div class="row"><span class="kbd" style="min-width:210px;text-align:center">${esc(k)}</span><span class="muted">${esc(d)}</span></div>`).join('')}</div></div>`;
    $$('[data-appearance]',el).forEach(button => button.onclick = () => {
      const theme = button.dataset.appearance;
      if (theme === 'system') { localStorage.removeItem('theme'); delete document.documentElement.dataset.theme; }
      else { localStorage.setItem('theme',theme); document.documentElement.dataset.theme = theme; }
      emit('appearance');
    });
    showAppearance();
    $('.logout', el).onclick = async () => { await api('/logout', {}); location.reload(); };
    const ib = $('.install', el);
    if (ib) ib.onclick = async () => { window.__sgInstall.prompt(); window.__sgInstall = null; };
    const ch = $('.chpw', el);
    if (ch) ch.onclick = () => changePassword();
  };
  draw();
  const offStatus = on('status', draw), offAppearance = on('appearance', showAppearance);
  return () => { offStatus(); offAppearance(); stopSecurity(); stopCare();stopUpdates(); stopFeatures(); stopNetwork(); };
}

async function changePassword() {
  const r = await modal({
    title: 'Change password', icon: 'settings',
    body: '<div class="col"><input class="input o" type="password" autocomplete="current-password" aria-label="Current password" placeholder="Current password"><input class="input n" type="password" autocomplete="new-password" aria-label="New password" placeholder="New password (12+ characters)"><input class="input c" autocomplete="one-time-code" aria-label="Authenticator or recovery code" placeholder="Authenticator code, if enabled"></div>',
    actions: [{ label: 'Cancel', value: null }, { label: 'Change', cls: 'primary', value: (bg) => ({ old: $('.o', bg).value, new: $('.n', bg).value,code:$('.c',bg).value.trim() }) }],
  });
  if (!r) return;
  try { await api('/password', r); toast('Password changed'); } catch (e) { fail(e); }
}
