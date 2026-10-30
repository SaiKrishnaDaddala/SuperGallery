// App shell: sidebar, natural-language search bar, task centre, login and hash routing.
import { $, $$, api, avatar, bytes, emit, esc, fail, h, icon, num, on, poll, stopPolling, setScope, state, userLabel } from './core.js';
import { peopleView } from './views/people.js';
import { albumsView } from './views/albums.js';
import { uploadsView } from './views/uploads.js';
import { categoriesView } from './views/categories.js';
import { usersView } from './views/users.js';
import { quickcleanView } from './views/quickclean.js';
import { dupfoldersView } from './views/dupfolders.js';
import { rulesView } from './views/rules.js';
import { filesView } from './views/files.js';
import { dashboardView } from './views/dashboard.js';
import { dashboardView as analyticsView } from './views/analytics.js';
import { openCommandPalette } from './commands.js';
import { presentSheet } from './sheet.js';
import { galleryView } from './views/gallery.js';
import { notifyIfUpdate } from './updates.js';
import { searchView } from './views/search.js';
import { duplicatesView } from './views/duplicates.js';
import { similarView } from './views/similar.js';
import { extensionsView } from './views/extensions.js';
import { cleanupView } from './views/cleanup.js';
import { trashView } from './views/trash.js';
import { organizeView } from './views/organize.js';
import { settingsView } from './views/settings.js';
import { applyFeatureVisibility, filteredNav, routeEnabled } from './features.js';

// Broken thumbnails fall back without inline handlers, so the page can run under a strict CSP.
document.addEventListener('error', (e) => {
  const img = e.target;
  if (!(img instanceof HTMLImageElement)) return;
  const fallback = img.dataset.fallback;
  if (fallback === 'remove') img.remove();
  else if (fallback === 'hide') img.style.visibility = 'hidden';
  else if (fallback === 'collapse') img.style.display = 'none';
  else if (fallback === 'icon') img.replaceWith(document.createRange().createContextualFragment(img.dataset.f || ''));
}, true);

if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('/sw.js').catch(() => {});

const ROUTES = {
  dashboard: dashboardView, analytics: analyticsView, files: filesView, gallery: galleryView, search: searchView, large: searchView,
  duplicates: duplicatesView, similar: similarView, categories: categoriesView, users: usersView, people: peopleView,
  quickclean: quickcleanView, dupfolders: dupfoldersView, rules: rulesView, extensions: extensionsView, cleanup: cleanupView,
  trash: trashView, organize: organizeView, settings: settingsView, albums: albumsView, uploads: uploadsView,
};
const NAV = [
  ['Library', [['dashboard', 'Library', 'dashboard'], ['gallery', 'Photos', 'images'], ['people', 'People', 'users'], ['albums', 'Smart albums', 'bookmark'], ['files', 'Files', 'folder'], ['uploads', 'Upload', 'upload']]],
  ['Organize', [['quickclean', 'Review', 'sparkles'], ['duplicates', 'Duplicates', 'copy', 'dup'], ['similar', 'Similar photos', 'layers', 'sim'], ['categories', 'Collections', 'tag'], ['analytics', 'Storage', 'pie']]],
  ['More tools', [['search', 'Search', 'search'], ['users', 'Library users', 'users'], ['large', 'Large files', 'hdd'], ['dupfolders', 'Duplicate folders', 'folder'], ['extensions', 'File types', 'fileText'], ['cleanup', 'Cleanup categories', 'broom'], ['rules', 'Automation', 'refresh'], ['organize', 'Organize files', 'wand']]],
];

let teardown = null;
let shellCleanup = () => {};
const TAB_KEYS = ['dashboard', 'gallery', 'files', 'quickclean', 'search'];
const tabLocations = new Map();
let closeTools = null;

function openTools() {
  if ($('.tools-sheet')) return;
  const previous = document.activeElement;
  const dialog = h(`<dialog class="tools-sheet" aria-labelledby="tools-title"><div class="sheet-grab" aria-hidden="true"><span></span></div><div class="sheet-title"><h2 id="tools-title">Your library</h2><button class="btn icon ghost done" aria-label="Close library tools">${icon('x')}</button></div><div class="tools-content">${filteredNav(NAV).map(([title, links]) => `<section><h3>${esc(title)}</h3><div class="tools-group">${links.map(([key,label,ic]) => `<a href="#/${key}">${icon(ic)}<span>${esc(label)}</span>${icon('right')}</a>`).join('')}</div></section>`).join('')}<section><h3>Manage</h3><div class="tools-group"><a href="#/trash">${icon('trash')}<span>Recently deleted</span>${icon('right')}</a><a href="#/settings">${icon('settings')}<span>Settings</span>${icon('right')}</a></div></section></div></dialog>`);
  document.body.append(dialog);
  closeTools = presentSheet(dialog, $('.sheet-grab',dialog));
  $('.done', dialog).onclick = closeTools;
  $$('a',dialog).forEach(a => a.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('close', () => { dialog.remove(); closeTools = null; previous?.focus(); }, {once:true});
}

function shell() {
  shellCleanup();
  document.body.innerHTML = '';
  const app = h(`<div id="app">
    <aside class="sidebar" id="navigation"><a class="brand" href="#/dashboard"><div class="logo"><img src="/static/icons/icon.svg" alt=""></div><span>SuperGallery<small>Your personal library</small></span></a>
      <nav class="nav" aria-label="Main navigation">${filteredNav(NAV).map(([sec, items], index) => `${index === 2 ? '<details class="more-tools"><summary>More tools ' + icon('down') + '</summary>' : '<h6>' + sec + '</h6>'}${items.map(([k, label, ic, badge]) => `<a href="#/${k}" data-k="${k}" title="${label}">${icon(ic)}<span>${label}</span>${badge ? `<span class="badge b-${badge} hidden"></span>` : ''}</a>`).join('')}${index === 2 ? '</details>' : ''}`).join('')}
        <div class="bm"></div></nav>
      <div class="side-foot"><a href="#/trash" data-k="trash">${icon('trash')}<span>Recently deleted</span><span class="badge b-trash hidden"></span></a><a href="#/settings" data-k="settings">${icon('settings')}<span>Settings</span></a><div class="library-health"><span class="status-dot"></span><span class="connection-label">Connecting to your NAS</span><button class="btn ghost sm icon collapse" title="Collapse sidebar" aria-label="Collapse sidebar">${icon('panel')}</button></div></div></aside>
    <button class="nav-scrim" aria-label="Close navigation"></button>
    <header class="topbar">
      <button class="btn icon ghost mobile-menu" aria-label="Browse library tools" aria-haspopup="dialog">${icon('panel')}</button>
      <span class="route-label">Library</span>
      <div class="search-box">${icon('search')}<input class="nlq" aria-label="Search your library" placeholder="Search your library"><button class="command-key" title="Search and commands (Ctrl+K)" aria-label="Open search and commands">⌘ K</button></div>
      <div class="scope-slot"></div>
      <span class="grow"></span>
      <div class="task-slot"></div>
      <button class="btn icon ghost theme" title="Toggle appearance" aria-label="Toggle appearance">${icon('sun')}</button>
      <button class="btn icon ghost mobile-search" aria-label="Search and commands">${icon('search')}</button>
    </header>
    <main id="main-content" tabindex="-1"></main><nav class="mobile-tabs" aria-label="Primary navigation">${[['dashboard','Library','dashboard'],['gallery','Photos','images'],['files','Files','folder'],['quickclean','Review','sparkles'],['search','Search','search']].map(([key,label,ic]) => `<a href="#/${key}" data-tab="${key}">${icon(ic)}<span>${label}</span></a>`).join('')}</nav></div>`);
  document.body.append(app);
  applyFeatureVisibility(app);
  const featureObserver=new MutationObserver(()=>applyFeatureVisibility(app));featureObserver.observe(app,{childList:true,subtree:true});
  const smallScreen = matchMedia('(max-width: 760px)');
  const updateMenu = () => { $('.sidebar', app).inert = smallScreen.matches; if (!smallScreen.matches) closeTools?.(); };
  smallScreen.addEventListener('change', updateMenu); updateMenu();
  $('.mobile-menu', app).onclick = openTools;
  $('.mobile-search', app).onclick = () => openCommandPalette(filteredNav(NAV));
  $('.command-key', app).onclick = () => openCommandPalette(filteredNav(NAV));
  if (localStorage.getItem('sidebar') === 'collapsed') app.classList.add('collapsed');
  $('.collapse', app).onclick = () => { app.classList.toggle('collapsed'); localStorage.setItem('sidebar', app.classList.contains('collapsed') ? 'collapsed' : ''); };
  const isDark = () => document.documentElement.dataset.theme === 'dark' || (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
  const updateAppearance = () => { $('.theme', app).innerHTML = icon(isDark() ? 'sun' : 'moon'); };
  $('.theme', app).onclick = () => {
    const t = isDark() ? 'light' : 'dark';
    document.documentElement.dataset.theme = t;
    localStorage.setItem('theme', t);
    emit('appearance');
  };
  $('.theme', app).innerHTML = icon(isDark() ? 'sun' : 'moon');
  const offAppearance = on('appearance', updateAppearance);
  const systemAppearance = matchMedia('(prefers-color-scheme: dark)');
  systemAppearance.addEventListener('change', updateAppearance);
  $$('.mobile-tabs a',app).forEach(a => a.onclick = () => {
    const currentTab = location.hash.slice(2).split(/[/?]/)[0];
    if (TAB_KEYS.includes(currentTab)) tabLocations.set(currentTab,location.hash);
    a.href = tabLocations.get(a.dataset.tab) || `#/${a.dataset.tab}`;
  });
  $('.command-key',app).textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K';
  const nlq = $('.nlq', app);
  nlq.onkeydown = (e) => {
    if (e.key === 'Enter' && nlq.value.trim()) { location.hash = '#/search?nl=' + encodeURIComponent(nlq.value.trim()); nlq.blur(); }
    if (e.key === 'Escape') nlq.blur();
  };
  const keyboard = (e) => {
    if (document.querySelector('dialog[open],.modal-bg,.lightbox')) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openCommandPalette(filteredNav(NAV)); return; }
    if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { e.preventDefault(); if (smallScreen.matches) openCommandPalette(filteredNav(NAV)); else nlq.focus(); }
  };
  document.addEventListener('keydown', keyboard);
  const offStatus = on('status', (ev) => renderStatus(ev.detail));
  const offScope = on('scope', () => { renderScope(); window.dispatchEvent(new HashChangeEvent('hashchange')); });
  loadUsers();
  const offPrefs = on('prefs', renderBookmarks);
  const offConnection = on('connection', ev => {
    const health = $('.connection-label');
    if (health && !ev.detail) health.textContent = 'Reconnecting to your NAS';
    $('.library-health')?.classList.toggle('offline', !ev.detail);
  });
  shellCleanup = () => { featureObserver.disconnect(); offStatus(); offScope(); offPrefs(); offConnection(); offAppearance(); smallScreen.removeEventListener('change', updateMenu); systemAppearance.removeEventListener('change', updateAppearance); document.removeEventListener('keydown', keyboard); };
  renderBookmarks();
}

async function loadUsers() {
  try { state.users = await api('/users'); } catch { state.users = []; }
  // forget selections of users that no longer exist
  if (state.scope) {
    const known = new Set(state.users.map((u) => u.name));
    const keep = state.scope.filter((u) => known.has(u));
    if (keep.length !== state.scope.length) setScope(keep);
  }
  renderScope();
  emit('users-loaded');
}

function renderScope() {
  const slot = $('.scope-slot');
  if (!slot) return;
  const sel = state.scope;
  const names = sel || state.users.map((u) => u.name);
  const label = !sel ? 'All users' : sel.length === 1 ? userLabel(sel[0]) : `${sel.length} users`;
  slot.innerHTML = `<button class="scope-btn" title="Choose which users to work with">
    <span class="stack">${names.slice(0, 3).map((n) => avatar(n)).join('') || avatar('?')}</span>
    <span class="lbl">${esc(label)}</span>${icon('down')}</button>`;
  $('.scope-btn', slot).onclick = (e) => openScopePicker(e.currentTarget);
}

function openScopePicker(anchor) {
  $('.scope-pop')?.remove();
  const users = state.users;
  let picked = new Set(state.scope || users.map((u) => u.name));
  const pop = h('<div class="scope-pop"></div>');
  const draw = () => {
    const all = picked.size === users.length;
    pop.innerHTML = `<div class="row" style="padding:6px 10px 8px"><b class="grow" style="font-size:15px">Work with</b><span class="muted" style="font-size:12px">actions only touch these users</span></div>
      <div class="opt ${all ? 'on' : ''}" data-all="1"><span class="avatar lg" style="background:linear-gradient(145deg,#5ac8fa,#5e5ce6)">${icon('users').replace('class="i ', 'style="width:16px;height:16px" class="i ')}</span>
        <div class="grow"><div style="font-weight:650">All users</div><div class="muted" style="font-size:12px">Everything on the NAS</div></div><span class="tick">${icon('check')}</span></div><hr>
      ${users.map((u) => `<div class="opt ${picked.has(u.name) ? 'on' : ''}" data-u="${esc(u.name)}">${avatar(u.name, 'lg')}
        <div class="grow" style="min-width:0"><div class="ellipsis" style="font-weight:650">${esc(userLabel(u.name))}</div>
        <div class="muted" style="font-size:12px">${num(u.count)} files · ${bytes(u.size)}</div></div><span class="tick">${icon('check')}</span></div>`).join('')}
      <div class="row" style="padding:10px 6px 4px"><span class="faint grow" style="font-size:11.5px">Tip: Alt-click picks just one</span><button class="btn sm cancel">Cancel</button><button class="btn sm primary apply">Apply</button></div>`;
    $('[data-all]', pop).onclick = () => { picked = all ? new Set() : new Set(users.map((u) => u.name)); draw(); };
    $$('[data-u]', pop).forEach((o) => (o.onclick = (e) => {
      const n = o.dataset.u;
      if (e.altKey) picked = new Set([n]); else picked.has(n) ? picked.delete(n) : picked.add(n);
      draw();
    }));
    $('.cancel', pop).onclick = () => pop.remove();
    $('.apply', pop).onclick = () => {
      if (!picked.size) return;
      setScope(picked.size === users.length ? null : [...picked]);
      pop.remove();
    };
  };
  draw();
  document.body.append(pop);
  const r = anchor.getBoundingClientRect();
  pop.style.left = Math.min(r.left, innerWidth - 350) + 'px';
  pop.style.top = r.bottom + 8 + 'px';
  setTimeout(() => document.addEventListener('mousedown', function away(e) {
    if (!e.target.closest('.scope-pop,.scope-btn')) { pop.remove(); document.removeEventListener('mousedown', away); }
  }), 0);
}

function renderBookmarks() {
  const bm = $('.nav .bm');
  if (!bm) return;
  const list = state.prefs.bookmarks || [];
  bm.innerHTML = list.length ? `<h6>Bookmarks</h6>${list.map((b) => `<a href="#/files?path=${encodeURIComponent(b.path)}" title="${esc(b.path)}">${icon('bookmark')}<span class="ellipsis">${esc(b.name)}</span></a>`).join('')}` : '';
}

let drawerOpen = false;
function renderStatus(s) {
  const health = $('.connection-label');
  if (health) health.textContent = s.tasks.some(t => t.status === 'running') ? 'Updating your library' : 'Connected to your NAS';
  const running = s.tasks.filter((t) => t.status === 'running' || t.status === 'queued');
  const slot = $('.task-slot');
  if (slot) {
    const t = running[0];
    slot.innerHTML = t ? `<div class="task-indicator"><div class="spin"></div><span class="ellipsis">${esc(t.stage || t.label)}${t.total ? ` · ${Math.floor((100 * t.done) / t.total)}%` : ''}</span>${running.length > 1 ? `<span class="badge">+${running.length - 1}</span>` : ''}</div>`
      : `<button class="btn ghost sm icon" title="Activity" aria-label="Activity">${icon('tasks')}</button>`;
    slot.firstElementChild.onclick = () => { drawerOpen = !drawerOpen; renderDrawer(s); };
  }
  const tb = $('.b-trash');
  if (tb) { tb.textContent = num(s.trash_count); tb.classList.toggle('hidden', !s.trash_count); }
  if (drawerOpen) renderDrawer(s);
}

function renderDrawer(s) {
  let d = $('.drawer');
  if (!drawerOpen) { d?.remove(); return; }
  if (!d) {
    d = h('<div class="drawer"></div>');
    document.body.append(d);
    setTimeout(() => document.addEventListener('mousedown', function away(e) {
      if (!e.target.closest('.drawer,.task-slot')) { drawerOpen = false; d.remove(); document.removeEventListener('mousedown', away); }
    }), 0);
  }
  d.innerHTML = `<div class="row" style="margin-bottom:6px"><b class="grow">Activity</b><button class="btn sm rescan">${icon('refresh')}Rescan now</button></div>
    ${s.tasks.length ? '' : '<div class="muted" style="padding:12px 0">No activity yet</div>'}
    ${s.tasks.slice(0, 15).map((t) => {
      const pct = t.total ? Math.min(100, (100 * t.done) / t.total) : 0;
      const live = t.status === 'running' || t.status === 'queued';
      return `<div class="task"><div class="row"><b class="grow ellipsis">${esc(t.label)}</b>
        <span class="badge ${t.status === 'done' ? 'ok' : t.status === 'error' ? 'danger' : live ? 'accent' : ''}">${t.status}</span>
        ${live ? `<button class="btn sm ghost icon cancel" data-id="${t.id}" title="Cancel">${icon('x')}</button>` : ''}</div>
        ${live ? `<div class="muted" style="font-size:12.5px">${esc(t.stage)} ${t.message ? '· ' + esc(t.message) : ''}</div>
          <div class="progress ${t.total ? '' : 'indet'}"><div style="width:${pct}%"></div></div>` : `<div class="faint" style="font-size:12px">${t.status === 'error' ? esc(t.message) : new Date((t.ended || t.created) * 1000).toLocaleTimeString()}</div>`}</div>`;
    }).join('')}`;
  $('.rescan', d).onclick = () => api('/scan', {}).then(() => poll(true)).catch(fail);
  $$('.cancel', d).forEach((b) => (b.onclick = () => api(`/tasks/${b.dataset.id}/cancel`, {}).then(() => poll(true))));
}

function route() {
  const [path, qs] = location.hash.replace(/^#\/?/, '').split('?');
  const parts = path.split('/');
  const key = ROUTES[parts[0]] ? parts[0] : 'dashboard';
  if(!routeEnabled(key)) { location.replace('#/settings'); return; }
  const params = new URLSearchParams(qs || '');
  if (key === 'large' && !params.has('min')) params.set('preset', 'large');
  $$('.sidebar a[data-k]').forEach((a) => { a.classList.toggle('active', a.dataset.k === key); if (a.dataset.k === key) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  const active = $('.sidebar a.active');
  if (active?.closest('details')) active.closest('details').open = true;
  $('.route-label').textContent = active?.querySelector('span')?.textContent || 'SuperGallery';
  document.title = `${$('.route-label').textContent} — SuperGallery`;
  if (TAB_KEYS.includes(key)) tabLocations.set(key, location.hash);
  $$('.mobile-tabs a').forEach(a => { a.classList.toggle('active', a.dataset.tab === key); if (a.dataset.tab === key) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
  $('#app').dataset.route = key;
  $('#app').classList.remove('nav-open');
  $('.sidebar').inert = matchMedia('(max-width: 760px)').matches;
  teardown?.();
  const main = $('main');
  main.innerHTML = '';
  try { teardown = ROUTES[key](main, params, parts.slice(1)) || null; } catch (e) { console.error(e); fail(e); }
}

// Login backdrop: loose photos, clips, screenshots and documents line up and drop into their folders.
const SORT_FOLDERS = [
  { kind: 'photo', label: 'Photos', icon: 'image', x: 12 },
  { kind: 'video', label: 'Videos', icon: 'film', x: 37 },
  { kind: 'shot', label: 'Screenshots', icon: 'monitor', x: 63 },
  { kind: 'doc', label: 'Documents', icon: 'fileText', x: 88 },
];
const SORT_CARDS = [[6, 12, -14], [71, 9, 11], [28, 30, 8], [86, 34, -9], [47, 8, -6], [14, 44, 13], [62, 26, -12], [93, 15, 7],
  [36, 47, -10], [79, 50, 12], [4, 28, 9], [55, 40, -13], [22, 6, 6], [68, 44, 10], [41, 22, -8], [90, 52, -5]];
const SCENE_KEY = 'sg-login-scene-paused';
function scenePaused() { try { return localStorage.getItem(SCENE_KEY) === '1'; } catch { return false; } }
function wireSceneToggle() {
  const root = $('.login'), btn = $('.scene-toggle');
  if (!root || !btn) return;
  const paint = (paused) => {
    root.classList.toggle('paused', paused);
    btn.setAttribute('aria-pressed', String(paused));
    btn.innerHTML = `${icon(paused ? 'play' : 'pause')}<span>${paused ? 'Play animation' : 'Pause animation'}</span>`;
  };
  paint(scenePaused());
  btn.onclick = () => { const paused = !root.classList.contains('paused'); try { localStorage.setItem(SCENE_KEY, paused ? '1' : '0'); } catch { /* private mode */ } paint(paused); };
}

function loginScene() {
  queueMicrotask(wireSceneToggle);  // runs once the caller has put the markup on the page
  const cycle = 12, folders = SORT_FOLDERS.map((f, i) => `<div class="sort-folder ${f.kind}" style="--fx:${f.x};--i:${i}"><div class="sort-folder-back"></div><div class="sort-folder-front">${icon(f.icon)}</div><span>${f.label}</span></div>`).join('');
  const cards = SORT_CARDS.map(([x, y, r], i) => {
    const f = SORT_FOLDERS[i % 4], slot = Math.floor(i / 4);
    return `<div class="sort-card ${f.kind}" style="--x0:${x};--y0:${y};--r0:${r}deg;--fx:${f.x};--slot:${slot};--delay:${(-i * cycle / SORT_CARDS.length).toFixed(2)}s;--cycle:${cycle}s"><i></i></div>`;
  }).join('');
  return `<button type="button" class="scene-toggle"></button><div class="login-scene" aria-hidden="true"><div class="login-glow g1"></div><div class="login-glow g2"></div><div class="login-glow g3"></div><div class="login-grid"></div>${cards}${folders}</div>`;
}

async function login(setup = false) {
  stopPolling();
  teardown?.(); teardown = null; shellCleanup();
  window.onhashchange=null;
  document.body.innerHTML = `<main class="login">${loginScene()}<div class="card"><div class="brand" style="padding:0"><div class="logo"><img src="/static/icons/icon.svg" alt=""></div><span role="heading" aria-level="1">SuperGallery</span></div>
    ${setup ? '<p class="muted" style="margin-top:0">Welcome! Create the password that protects this app. It can delete files, so pick a strong one.</p>' : ''}
    <p class="login-welcome">Your memories. Beautifully in order.</p><form class="col"><input class="input p1" type="password" aria-label="Password" autocomplete="${setup ? 'new-password' : 'current-password'}" placeholder="${setup ? 'New password (12+ characters)' : 'Password'}" autofocus>
    ${setup ? '<input class="input p2" type="password" placeholder="Repeat password">' : ''}
    <button class="btn primary">${setup ? 'Create password' : 'Sign in'}</button><div class="err danger-text" role="alert"></div></form><p class="login-foot">${icon('lock')}Private to your NAS. Nothing leaves your network.</p></div></main>`;
  $('form').onsubmit = async (e) => {
    e.preventDefault();
    const pw = $('.p1').value;
    if (setup && pw !== $('.p2').value) { $('.err').textContent = 'Passwords do not match'; return; }
    const button=$('form .primary');button.disabled=true;
    try { const result=await api(setup ? '/setup' : '/login', { password: pw }); $('.p1').value=''; if(result.mfa_required) return loginCode(); boot(); } catch (err) { $('.err').textContent = err.message; } finally { button.disabled=false; }
  };
}

function loginCode() {
  const form=$('.login form');let recovery=false;
  form.innerHTML='<h2>Two-step verification</h2><p class="muted code-help">Enter the six-digit code from your authenticator app.</p><input class="input otp-input code" aria-label="Verification code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000"><button class="btn primary">Verify and sign in</button><button type="button" class="btn ghost recovery">Use a recovery code</button><button type="button" class="btn ghost back">Back to password</button><p class="err danger-text" role="alert"></p>';
  $('.code',form).focus();
  $('.back',form).onclick=()=>login();
  $('.recovery',form).onclick=()=>{recovery=!recovery;const input=$('.code',form);input.value='';input.inputMode=recovery?'text':'numeric';input.maxLength=recovery?40:6;input.placeholder=recovery?'Recovery code':'000000';input.classList.toggle('otp-input',!recovery);$('.code-help',form).textContent=recovery?'Enter one of your saved recovery codes. Each code works only once.':'Enter the six-digit code from your authenticator app.';$('.recovery',form).textContent=recovery?'Use authenticator instead':'Use a recovery code';input.focus();};
  form.onsubmit=async e=>{e.preventDefault();const button=$('.primary',form);button.disabled=true;$('.err',form).textContent='';try{await api('/login/verify',{code:$('.code',form).value.trim()});$('.code',form).value='';boot();}catch(error){$('.err',form).textContent=error.message;}finally{button.disabled=false;}};
}

async function boot() {
  const a = await api('/auth');
  if(a.https_required){teardown?.();shellCleanup();document.body.innerHTML=`<main class="login">${loginScene()}<div class="card"><h1>Secure sign-in</h1><p>Two-step verification is enabled. Continue using the encrypted connection to your NAS.</p><a class="btn primary" href="${esc(a.secure_url.replace('#/settings',location.hash||'#/dashboard'))}">Open secure SuperGallery</a></div></main>`;return;}
  if (!a.ok) return login(a.setup);
  try { state.prefs = { bookmarks: [], ...(await api('/prefs')) }; } catch { /* first run */ }
  state.features = (await api('/features')).values;
  shell();
  setTimeout(notifyIfUpdate, 1500);
  await poll();
  window.onhashchange = route;
  route();
}

function secureConnection() {
  if (document.querySelector('.secure-connect')) return;
  const target = new URL(location.href); target.protocol = 'https:'; target.port = '8843';
  const notice = h(`<aside class="secure-connect" role="status"><div><strong>Open the secure connection</strong><p>Your browser may require HTTPS to access your NAS. Use the encrypted app address, or retry when your NAS is reachable.</p></div><a class="btn primary" href="${esc(target.href)}">Open secure SuperGallery</a></aside>`);
  document.body.append(notice);
}

window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); window.__sgInstall = e; });
if (localStorage.getItem('theme')) document.documentElement.dataset.theme = localStorage.getItem('theme');
on('auth', () => boot());
on('features',()=>{ if(!document.querySelector('#app'))return;applyFeatureVisibility();if(!location.hash.startsWith('#/settings'))route(); });
on('secure-connection', secureConnection);
window.addEventListener('offline',()=>{if(!document.querySelector('.connection-notice'))document.body.append(h('<div class="connection-notice" role="status">Connection lost. Reconnect to your NAS to continue. Uploads can be resumed.</div>'));});
window.addEventListener('online',()=>document.querySelector('.connection-notice')?.remove());
on('changed', (e) => { if (e.detail?.kind === 'index') { emit('indexed'); loadUsers(); } });
boot().catch(error => {
  if (!document.body.querySelector('.login,#app')) document.body.innerHTML = `<main class="login">${loginScene()}<div class="card"><h1>Connect to your NAS</h1><p>${esc(error.message)}</p><button class="btn primary retry-connect">Try again</button></div></main>`;
  document.querySelector('.retry-connect')?.addEventListener('click',()=>location.reload());
  if(location.protocol==='http:') secureConnection();
});
