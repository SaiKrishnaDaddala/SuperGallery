// Core helpers shared by every view: DOM, formatting, API, overlays, background tasks.

// ---------------------------------------------------------------- icons (Lucide-style paths)
const P = {
  lock: '<rect x="4" y="10" width="16" height="11" rx="3"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  folder: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>',
  folderOpen: '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
  folderPlus: '<path d="M12 10v6M9 13h6"/><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
  images: '<path d="M18 22H4a2 2 0 0 1-2-2V6"/><path d="m22 13-1.3-1.3a2.4 2.4 0 0 0-3.4 0L11 18"/><circle cx="12" cy="8" r="2"/><rect x="6" y="2" width="16" height="16" rx="2"/>',
  video: '<path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 11"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M3 7.5h4M3 12h18M3 16.5h4M17 3v18M17 7.5h4M17 16.5h4"/>',
  music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
  fileText: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4M10 9H8M16 13H8M16 17H8"/>',
  archive: '<rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8M10 12h4"/>',
  code: '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
  package: '<path d="m7.5 4.27 9 5.15M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/>',
  copy: '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65M22 12.65l-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="3"/><path d="m16 16-1.9-1.9"/>',
  pie: '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
  bars: '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
  sparkles: '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.29 1.29L3 12l5.8 1.9a2 2 0 0 1 1.29 1.29L12 21l1.9-5.8a2 2 0 0 1 1.29-1.29L21 12l-5.8-1.9a2 2 0 0 1-1.29-1.29Z"/><path d="M5 3v4M19 17v4M3 5h4M17 19h4"/>',
  broom: '<path d="m13 11 9-9M14.6 12.6c.8.8.9 2.1.2 3L10 22l-8-8 6.4-4.8c.9-.7 2.2-.6 3 .2Z"/><path d="m6.8 10.4 6.8 6.8M5 17l1.4-1.4"/>',
  trash: '<path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2M10 11v6M14 11v6"/>',
  restore: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  up: '<path d="m18 15-6-6-6 6"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  arrowUp: '<path d="m5 12 7-7 7 7M12 19V5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
  columns: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v18"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/>',
  edit: '<path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  scissors: '<circle cx="6" cy="6" r="3"/><path d="M8.12 8.12 12 12M20 4 8.12 15.88"/><circle cx="6" cy="18" r="3"/><path d="M14.8 14.8 20 20"/>',
  clipboard: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
  move: '<path d="M5 9l-3 3 3 3M9 5l3-3 3 3M15 19l-3 3-3-3M19 9l3 3-3 3M2 12h20M12 2v20"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>',
  star: '<path d="M11.5 2.3a.53.53 0 0 1 1 0l2.3 4.7a2.1 2.1 0 0 0 1.6 1.2l5.2.7a.53.53 0 0 1 .3.9l-3.8 3.7a2.1 2.1 0 0 0-.6 1.9l.9 5.2a.53.53 0 0 1-.8.6l-4.6-2.5a2.1 2.1 0 0 0-2 0l-4.7 2.5a.53.53 0 0 1-.8-.6l.9-5.2a2.1 2.1 0 0 0-.6-1.9L1.6 9.8a.53.53 0 0 1 .3-.9l5.2-.7A2.1 2.1 0 0 0 8.7 7Z"/>',
  play: '<path d="m6 3 14 9-14 9z"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  hdd: '<path d="M22 12H2M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11zM6 16h.01M10 16h.01"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68M6.61 6.61A13.53 13.53 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61M2 2l20 20"/>',
  filter: '<path d="M22 3H2l8 9.46V19l4 2v-8.54z"/>',
  wand: '<path d="m15 4-1 1M21 10l-1 1M17.5 2.5 21.5 6.5M3 21l12-12M14 6l4 4"/><path d="M9 3v2M5 7H3M21 15h-2M15 21v-2"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
  blur: '<circle cx="12" cy="12" r="10" stroke-dasharray="3 3"/><circle cx="12" cy="12" r="4"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  minimize: '<path d="M8 3v3a2 2 0 0 1-2 2H3M21 8h-3a2 2 0 0 1-2-2V3M3 16h3a2 2 0 0 1 2 2v3M16 21v-3a2 2 0 0 1 2-2h3"/>',
  monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
  hourglass: '<path d="M5 22h14M5 2h14M17 22v-4.17a2 2 0 0 0-.59-1.42L12 12l-4.41 4.41A2 2 0 0 0 7 17.83V22M7 2v4.17a2 2 0 0 0 .59 1.42L12 12l4.41-4.41A2 2 0 0 0 17 6.17V2"/>',
  zip: '<path d="M10 12v-1M10 18v-2M10 7V6M14 2v4a2 2 0 0 0 2 2h4"/><path d="M15.5 22H18a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h2.5"/><circle cx="10" cy="20" r="2"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  sort: '<path d="m21 16-4 4-4-4M17 20V4M3 8l4-4 4 4M7 4v16"/>',
  tasks: '<path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>',
  bookmark: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
  zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
  expand: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
  selectAll: '<path d="M5 3a2 2 0 0 0-2 2M19 3a2 2 0 0 1 2 2M21 19a2 2 0 0 1-2 2M5 21a2 2 0 0 1-2-2M9 3h1M9 21h1M14 3h1M14 21h1M3 9v1M21 9v1M3 14v1M21 14v1"/><path d="m9 12 2 2 4-4"/>',
  invert: '<circle cx="12" cy="12" r="10"/><path d="M12 2v20a10 10 0 0 0 0-20Z" fill="currentColor"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  tag: '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
  brain: '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4M17.599 6.5a3 3 0 0 0 .399-1.375M6.003 5.125A3 3 0 0 0 6.401 6.5M3.477 10.896a4 4 0 0 1 .585-.396M19.938 10.5a4 4 0 0 1 .585.396M6 18a4 4 0 0 1-1.967-.516M19.967 17.484A4 4 0 0 1 18 18"/>',
};
export function icon(name, cls = '') {
  return `<svg class="i ${cls}" viewBox="0 0 24 24">${P[name] || P.file}</svg>`;
}

// ---------------------------------------------------------------- DOM / format
export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];
export function h(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function bytes(n, d = 1) {
  if (n == null) return '—';
  if (n < 1024) return `${Math.round(n)} B`;
  const u = ['KB', 'MB', 'GB', 'TB', 'PB'];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n >= 100 ? 0 : d)} ${u[i]}`;
}
export const num = (n) => (n ?? 0).toLocaleString();
export function dur(s) {
  if (!s && s !== 0) return '';
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}` : `${m}:${String(x).padStart(2, '0')}`;
}
export function date(ts, withTime = false) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return withTime ? d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
export function ago(ts) {
  if (!ts) return 'never';
  const s = Date.now() / 1000 - ts;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} days ago`;
}
export const basename = (p) => p.replace(/\/+$/, '').split('/').pop();
export const dirname = (p) => p.replace(/\/+$/, '').split('/').slice(0, -1).join('/') || '/';
export function shortPath(p) {
  const roots = state.status?.roots || [];
  for (const r of roots) if (p === r || p.startsWith(r + '/')) return (basename(r) + p.slice(r.length)) || p;
  return p;
}
export function parseSize(s) {
  const m = String(s).trim().toLowerCase().match(/^([\d.]+)\s*(b|kb?|mb?|gb?|tb?)?$/);
  if (!m) return null;
  const u = { b: 1, k: 1024, kb: 1024, m: 1 << 20, mb: 1 << 20, g: 1 << 30, gb: 1 << 30, t: 2 ** 40, tb: 2 ** 40 }[m[2] || 'mb'];
  return Math.round(parseFloat(m[1]) * u);
}
export const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

export const CAT_COLORS = {
  image: '#007aff', video: '#ff2d55', audio: '#ff9500', document: '#34c759', archive: '#af52de',
  code: '#5ac8fa', app: '#ff3b30', other: '#8e8e93', folder: '#1e9bff', volume: '#007aff',
};
export const CAT_LABEL = { image: 'Photos & images', video: 'Videos', audio: 'Music & audio', document: 'Documents', archive: 'Archives', code: 'Code', app: 'Apps & installers', other: 'Other' };
export const CAT_ICON = { image: 'image', video: 'film', audio: 'music', document: 'fileText', archive: 'archive', code: 'code', app: 'package', other: 'file', folder: 'folder', volume: 'hdd' };
const EXT_COLORS = { pdf: '#ef4444', doc: '#2563eb', docx: '#2563eb', xls: '#16a34a', xlsx: '#16a34a', csv: '#16a34a', ppt: '#ea580c', pptx: '#ea580c', txt: '#64748b', md: '#64748b', zip: '#8b5cf6', rar: '#8b5cf6', '7z': '#8b5cf6', iso: '#7c3aed', exe: '#e11d48', apk: '#65a30d' };
export function extColor(ext, cat) { return EXT_COLORS[ext] || CAT_COLORS[cat] || CAT_COLORS.other; }

export const THUMBABLE = new Set('jpg jpeg jfif png gif bmp webp tif tiff ico heic heif avif mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp ts mts m2ts vob ogv'.split(' '));
export const thumbUrl = (it, s = 256) => it.id ? `/api/thumb?id=${it.id}&s=${s}` : `/api/thumb?path=${encodeURIComponent(it.path)}&s=${s}`;
export const rawUrl = (it, dl = false) => (it.id ? `/api/raw?id=${it.id}` : `/api/raw?path=${encodeURIComponent(it.path)}`) + (dl ? '&download=1' : '');

export function fileIcon(it, big = false) {
  // Index rows carry dir as the parent path, not a flag, so only a literal true means folder.
  if (it.dir === true || it.cat === 'folder') return `<div class="${big ? 'big-ic' : 'ficon'}" style="background:${CAT_COLORS.folder}">${icon(it.cat === 'volume' ? 'hdd' : 'folder')}</div>`;
  const c = extColor(it.ext, it.cat);
  if (!big && THUMBABLE.has(it.ext) && it.cat === 'image') return `<div class="ficon" style="background:${c}"><img loading="lazy" alt="" src="${thumbUrl(it)}" data-fallback="remove"></div>`;
  const label = it.ext ? it.ext.slice(0, 4) : '';
  if (big || !label) return `<div class="${big ? 'big-ic' : 'ficon'}" style="background:${c}">${icon(CAT_ICON[it.cat] || 'file')}</div>`;
  // Text labels sit on a darker shade of the colour so white text stays readable (WCAG AA).
  return `<div class="ficon" style="background:color-mix(in srgb,${c} 60%,#000)">${esc(label)}</div>`;
}

// ---------------------------------------------------------------- state & API
function loadScope() {
  try { const v = JSON.parse(localStorage.getItem('sg-scope') || 'null'); return Array.isArray(v) && v.length ? v : null; } catch { return null; }
}
export const state = { status: null, features: {}, prefs: { bookmarks: [] }, clipboard: null, scope: loadScope(), users: [] };

/** Users the whole app is limited to (null = everyone). */
export function setScope(list) {
  state.scope = list && list.length ? [...list] : null;
  try { localStorage.setItem('sg-scope', JSON.stringify(state.scope)); } catch { /* private mode */ }
  emit('scope', state.scope);
}
const AV_COLORS = ['#007aff', '#ff2d55', '#34c759', '#ff9500', '#af52de', '#5ac8fa', '#ff3b30', '#5856d6', '#30b0c7', '#a2845e'];
export function userColor(name) {
  if (name === 'shared') return '#8e8e93';
  let h = 0;
  for (const c of String(name)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return AV_COLORS[h % AV_COLORS.length];
}
export const userLabel = (name) => (name === 'shared' ? 'Shared folders' : name);
export function avatar(name, cls = '') {
  const g = name === 'shared' ? '<svg class="i" viewBox="0 0 24 24" style="width:13px;height:13px"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>' : esc(String(name).slice(0, 1));
  return `<span class="avatar ${cls}" style="background:${userColor(name)}">${g}</span>`;
}
export const ownerChip = (name) => (name ? `<span class="owner-chip">${avatar(name)}${esc(userLabel(name))}</span>` : '');
const bus = new EventTarget();
export const on = (ev, fn) => { bus.addEventListener(ev, fn); return () => bus.removeEventListener(ev, fn); };
export const emit = (ev, detail) => bus.dispatchEvent(new CustomEvent(ev, { detail }));

// FastAPI validation errors arrive as a list of {loc, msg}; turn any detail into a readable sentence.
function errorText(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const field = Array.isArray(d?.loc) ? d.loc.filter((x) => x !== 'body' && x !== 'query').join(' ') : '';
      return (field ? field.replace(/_/g, ' ') + ': ' : '') + (d?.msg || 'invalid value');
    }).join('; ') || 'The request was not accepted.';
  }
  return detail?.msg || detail?.message || 'The request was not accepted.';
}

export async function api(path, body, method) {
  const opt = { method: method || (body !== undefined ? 'POST' : 'GET'), headers: {'X-SG-Request':'1'} };
  if (state.scope) opt.headers['X-SG-Users'] = state.scope.map(encodeURIComponent).join(',');
  if (body !== undefined && !(body instanceof FormData)) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  else if (body instanceof FormData) opt.body = body;
  let r;
  try { r = await fetch('/api' + path, opt); }
  catch (error) {
    if (location.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)) emit('secure-connection');
    throw new Error('Could not connect to your NAS. Check your connection or use the secure app address.');
  }
  if (r.status === 401) { stopPolling(); if (!document.querySelector('.login')) emit('auth'); throw new Error('Login required'); }
  if (r.status === 426 && !document.querySelector('.login')) { stopPolling(); emit('auth'); }
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch { /* not json */ }
    throw new Error(errorText(msg));
  }
  const ct = r.headers.get('content-type') || '';
  return ct.includes('json') ? r.json() : r.text();
}

export async function savePrefs() { await api('/prefs', state.prefs, 'PUT'); emit('prefs'); }

// ---------------------------------------------------------------- toasts
export function toast(msg, kind = 'ok', ms = 4200) {
  let box = $('.toasts');
  if (!box) { box = h('<div class="toasts" aria-live="polite" aria-atomic="false"></div>'); document.body.append(box); }
  const t = h(`<div class="toast ${kind}">${icon(kind === 'err' ? 'alert' : kind === 'info' ? 'info' : 'check')}<div>${msg}</div></div>`);
  box.append(t);
  setTimeout(() => t.remove(), ms);
}
export const fail = (e) => toast(esc(e.message || e), 'err', 6000);

// ---------------------------------------------------------------- modals
export function containDialogFocus(dialog) {
  dialog.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    const controls = $$('a[href],button,input,select,textarea,video[controls],audio[controls],[tabindex="0"]', dialog)
      .filter(control => !control.disabled && control.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (!first) { e.preventDefault(); return; }
    if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || document.activeElement === dialog)) { e.preventDefault(); first.focus(); }
  });
}
export function modal({ title, body, actions = [], wide = false, onOpen, icon: ic }) {
  return new Promise((resolve) => {
    const previous = document.activeElement;
    const bg = h(`<dialog class="modal-bg" aria-label="${esc(title)}"><div class="modal ${wide ? 'wide' : ''}">
      <h2 class="modal-h">${ic ? icon(ic) : ''}${esc(title)}</h2><div class="modal-b"></div><div class="modal-f"></div></div></dialog>`);
    const b = $('.modal-b', bg);
    if (typeof body === 'string') b.innerHTML = body; else if (body) b.append(body);
    let closed = false;
    const close = (v) => { if (closed) return; closed = true; bg.close(); bg.remove(); document.removeEventListener('keydown', key, true); window.removeEventListener('hashchange', away); previous?.focus(); resolve(v); };
    // Leaving the page (Back button, a link) cancels the dialog instead of leaving it over the next page.
    const away = () => close(null);
    window.addEventListener('hashchange', away);
    for (const a of actions) {
      const btn = h(`<button class="btn ${a.cls || ''}">${a.icon ? icon(a.icon) : ''}${esc(a.label)}</button>`);
      btn.onclick = async () => {
        if (a.validate && !(await a.validate(bg))) return;
        close(a.value !== undefined ? (typeof a.value === 'function' ? a.value(bg) : a.value) : a.label);
      };
      $('.modal-f', bg).append(btn);
    }
    const key = (e) => {
      if (!bg.contains(e.target)) return;
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(null); }
      if (e.key === 'Enter' && !e.shiftKey && e.target.tagName === 'INPUT' && !['checkbox','radio'].includes(e.target.type)) {
        const p = $$('.modal-f .btn', bg).pop();
        if (p) { e.preventDefault(); e.stopPropagation(); p.click(); }
      }
    };
    document.addEventListener('keydown', key, true);
    bg.addEventListener('mousedown', (e) => { if (e.target === bg) close(null); });
    bg.addEventListener('cancel', (e) => { e.preventDefault(); close(null); });
    document.body.append(bg);
    containDialogFocus(bg);
    bg.showModal();
    onOpen?.(bg, close);
    const f = $('input,select,textarea,.modal-f .btn', bg);
    if (f && !closed) { f.focus(); f.select?.(); }
  });
}
export const confirmBox = (title, html, okLabel = 'OK', danger = false) =>
  modal({ title, body: html, icon: danger ? 'alert' : 'info', actions: [{ label: 'Cancel', value: false }, { label: okLabel, cls: danger ? 'danger' : 'primary', value: true }] });
export async function prompt(title, value = '', label = '') {
  return modal({
    title, body: `${label ? `<div class="muted" style="margin-bottom:8px">${esc(label)}</div>` : ''}<input class="input" style="width:100%" value="${esc(value)}">`,
    actions: [{ label: 'Cancel', value: null }, { label: 'OK', cls: 'primary', value: (bg) => $('input', bg).value }],
    onOpen: (bg) => {
      const i = $('input', bg);
      const dot = value.lastIndexOf('.');
      setTimeout(() => i.setSelectionRange(0, dot > 0 ? dot : value.length), 40);
    },
  });
}

/** Confirm + submit a delete. `what` = {ids|paths|filter, count, size, guard, reason}. Returns task promise or null. */
export async function confirmDelete(what) {
  const days = state.status?.trash_days ?? 30;
  const body = h(`<div class="col" style="gap:14px">
    <div style="font-size:15px">Delete <b>${num(what.count)}</b> item${what.count === 1 ? '' : 's'}${what.size != null ? ` · <b>${bytes(what.size)}</b>` : ''}?</div>
    ${what.extra || ''}
    <div class="notice info">${icon('restore')}<div>Files go to the <b>Recycle bin</b> on the same volume (instant, no copying). You can restore them for ${days} days.</div></div>
    ${what.guard ? `<div class="notice info">${icon('check')}<div>Safety lock on: at least one copy of every group is always kept, even if every file is selected.</div></div>` : ''}
    <label class="chk"><input type="checkbox" class="perm"> Delete permanently instead (cannot be undone)</label>
  </div>`);
  const r = await modal({
    title: 'Delete files', body, icon: 'trash',
    actions: [{ label: 'Cancel', value: null }, { label: 'Delete', cls: 'danger', icon: 'trash', value: (bg) => ({ permanent: $('.perm', bg).checked }) }],
  });
  if (!r) return null;
  if (r.permanent && !(await confirmBox('Permanently delete?', `<b>${num(what.count)}</b> items will be erased forever. This cannot be undone.`, 'Erase forever', true))) return null;
  const payload = { ids: what.ids, paths: what.paths, filter: what.filter, guard: what.guard, permanent: r.permanent, reason: what.reason };
  return runTask(api('/delete', payload));
}

// ---------------------------------------------------------------- context menu
export function contextMenu(x, y, items) {
  closeContext();
  const m = h('<div class="ctx"></div>');
  for (const it of items) {
    if (!it) continue;
    if (it === '-') { m.append(h('<hr>')); continue; }
    const b = h(`<button class="${it.danger ? 'danger' : ''}" ${it.disabled ? 'disabled style="opacity:.4"' : ''}>${icon(it.icon || 'file')}<span>${esc(it.label)}</span>${it.key ? `<span class="k">${esc(it.key)}</span>` : ''}</button>`);
    b.onclick = () => { closeContext(); if (!it.disabled) it.run(); };
    m.append(b);
  }
  document.body.append(m);
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth - r.width - 8) + 'px';
  m.style.top = Math.min(y, innerHeight - r.height - 8) + 'px';
  setTimeout(() => document.addEventListener('mousedown', ctxAway, true), 0);
}
function ctxAway(e) { if (!e.target.closest('.ctx')) closeContext(); }
export function closeContext() { $('.ctx')?.remove(); document.removeEventListener('mousedown', ctxAway, true); }

// ---------------------------------------------------------------- background tasks
const waiters = new Map();
let pollTimer = null;
let pollGeneration = 0;
const taskStates = new Map();
let sawTasks = false;
export function stopPolling() { clearTimeout(pollTimer); pollGeneration++; }
export async function runTask(p, { silent = false } = {}) {
  let r;
  try { r = await p; } catch (e) { fail(e); return null; }
  if (!r?.task) return r;
  return new Promise((resolve) => { waiters.set(r.task, { resolve, silent }); poll(true); });
}
export async function poll(soon = false) {
  const generation = pollGeneration;
  clearTimeout(pollTimer);
  if (soon) { pollTimer = setTimeout(poll, 400); return; }
  try {
    state.status = await api('/status');
      if (generation !== pollGeneration) return;
    if(state.status.features && JSON.stringify(state.features)!==JSON.stringify(state.status.features)) {state.features=state.status.features;emit('features',state.features);}
    emit('connection', true);
    emit('status', state.status);
    for (const t of state.status.tasks) {
        const complete = ['done', 'error', 'cancelled'].includes(t.status);
        if (sawTasks && complete && taskStates.get(t.id) !== t.status) emit('changed', t);
        taskStates.set(t.id, t.status);
      const w = waiters.get(t.id);
      if (w && ['done', 'error', 'cancelled'].includes(t.status)) {
        waiters.delete(t.id);
        if (!w.silent) taskToast(t);
        w.resolve(t);
      }
      sawTasks = true;
    }
  } catch { emit('connection', false); }
  if (generation !== pollGeneration) return;
  const busy = state.status?.tasks.some((t) => t.status === 'running' || t.status === 'queued');
  pollTimer = setTimeout(poll, busy || waiters.size ? 1200 : 8000);
}
function taskToast(t) {
  if (t.status === 'error') return toast(`${esc(t.label)} failed: ${esc(t.message)}`, 'err', 8000);
  if (t.status === 'cancelled') return toast(`${esc(t.label)} cancelled`, 'info');
  const r = t.result || {};
  let msg = esc(t.label) + ' — done';
  if (r.deleted != null) msg = `${r.permanent ? 'Deleted' : 'Moved to recycle bin'}: <b>${num(r.deleted)}</b> items · ${bytes(r.freed)}`;
  if (r.moved != null) msg = `Moved <b>${num(r.moved)}</b> items`;
  if (r.restored != null) msg = `Restored <b>${num(r.restored)}</b> items`;
  if (r.purged != null) msg = `Freed ${bytes(r.freed)} (${num(r.purged)} items erased)`;
  if (r.renamed != null) msg = `Renamed <b>${num(r.renamed)}</b> items`;
  if (r.error_count) msg += ` <span class="danger-text">· ${num(r.error_count)} failed</span>`;
  toast(msg, r.error_count ? 'err' : 'ok', r.error_count ? 8000 : 4200);
}

// ---------------------------------------------------------------- folder picker
export async function pickFolder(title = 'Choose folder', start = '') {
  let cur = start || '';
  const body = h(`<div class="col"><div class="row"><button class="btn sm icon up">${icon('arrowUp')}</button><div class="mono grow ellipsis cur"></div>
    <button class="btn sm nf">${icon('folderPlus')}New folder</button></div><div class="tree"></div></div>`);
  const load = async () => {
    const d = await api('/browse?path=' + encodeURIComponent(cur));
    $('.cur', body).textContent = cur ? shortPath(cur) : 'All volumes';
    const tree = $('.tree', body);
    tree.innerHTML = '';
    const dirs = d.entries.filter((e) => e.dir).sort((a, b) => a.name.localeCompare(b.name));
    if (!dirs.length) tree.innerHTML = '<div class="muted" style="padding:10px">No sub-folders</div>';
    for (const e of dirs) {
      const n = h(`<div class="tn">${icon(e.cat === 'volume' ? 'hdd' : 'folder')}<span class="grow ellipsis">${esc(e.name)}</span><span class="faint">${bytes(e.size)}</span></div>`);
      n.onclick = () => { cur = e.path; load(); };
      tree.append(n);
    }
    $('.up', body).disabled = !cur;
    $('.nf', body).disabled = !cur;
    $('.up', body).onclick = () => { cur = d.parent || ''; load(); };
  };
  $('.nf', body).onclick = async () => {
    const n = await prompt('New folder', 'New folder');
    if (n) { try { await api('/mkdir', { parent: cur, name: n }); load(); } catch (e) { fail(e); } }
  };
  await load().catch(fail);
  return modal({
    title, body, icon: 'folderOpen',
    actions: [{ label: 'Cancel', value: null }, { label: 'Select this folder', cls: 'primary', value: () => cur, validate: () => !!cur || (toast('Open a folder first', 'info'), false) }],
  });
}

// ---------------------------------------------------------------- tooltip
let tipEl;
export function tip(e, html) {
  if (!tipEl) { tipEl = h('<div class="tip"></div>'); document.body.append(tipEl); }
  if (!html) { tipEl.style.display = 'none'; return; }
  tipEl.innerHTML = html;
  tipEl.style.display = 'block';
  const r = tipEl.getBoundingClientRect();
  tipEl.style.left = Math.min(e.clientX + 14, innerWidth - r.width - 6) + 'px';
  tipEl.style.top = Math.min(e.clientY + 14, innerHeight - r.height - 6) + 'px';
}
