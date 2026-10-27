// Advanced file manager: dual pane, virtualised list/grid (100k+ entries), keyboard driven,
// drag & drop, clipboard, bulk rename, zip/unzip, uploads, live preview and folder-size insight.
import {
  $, $$, api, basename, bytes, closeContext, confirmBox, confirmDelete, contextMenu, date, debounce, dirname, emit,
  esc, fail, fileIcon, h, icon, modal, num, on, pickFolder, prompt, rawUrl, runTask, savePrefs, shortPath, state,
  THUMBABLE, thumbUrl, toast,
} from '../core.js';
import { hasFeature } from '../features.js';
import { hbars } from '../charts.js';
import { lightbox } from '../lightbox.js';

const ROW = 34;
const compactFiles = () => matchMedia('(max-width: 760px)').matches;
const TEXT_EXT = new Set('txt md log json xml csv tsv yml yaml ini conf cfg py js ts jsx tsx html htm css sh bat ps1 c cpp h java go rs php rb sql srt nfo env toml'.split(' '));
const ARCHIVES = /\.(zip|tar|tgz|tar\.gz|tar\.bz2|tar\.xz)$/i;
const MEDIA = new Set(['image', 'video', 'audio']);
const COLS = 'minmax(220px,1fr) 150px 120px 160px';

const prefs = () => (state.prefs.fm ||= { mode: 'list', tile: 150, hidden: false, dual: false, preview: true, sort: 'name', dir: 'asc' });

class Pane {
  constructor(fm, idx) {
    this.fm = fm;
    this.idx = idx;
    this.path = '';
    this.entries = [];
    this.list = [];
    this.sel = new Set();
    this.focus = -1;
    this.anchor = -1;
    this.back = [];
    this.fwd = [];
    this.filter = '';
    this.data = null;
    this.el = h(`<div class="pane">
      <div class="pane-head">
        <button class="btn icon sm ghost b-back" title="Back (Alt+←)">${icon('left')}</button>
        <button class="btn icon sm ghost b-fwd" title="Forward (Alt+→)">${icon('right')}</button>
        <button class="btn icon sm ghost b-up" title="Up (Backspace)">${icon('arrowUp')}</button>
        <div class="crumbs" title="Click empty space to type a path"></div>
        <input class="input sm qf" aria-label="Filter this folder" placeholder="Filter…  (*.jpg)" style="width:150px">
        <button class="btn icon sm ghost b-star" title="Bookmark this folder">${icon('star')}</button>
      </div>
      <div class="vl" tabindex="0"><div class="vl-head" style="grid-template-columns:${COLS}"></div><div class="vl-inner"></div></div>
      <div class="status"></div></div>`);
    this.vl = $('.vl', this.el);
    this.inner = $('.vl-inner', this.el);
    this.head = $('.vl-head', this.el);
    this.bind();
  }

  get mode() { return prefs().mode; }
  get selected() { return this.list.filter((e) => this.sel.has(e.path)); }
  get focused() { return this.list[this.focus]; }

  bind() {
    $('.b-back', this.el).onclick = () => this.history(-1);
    $('.b-fwd', this.el).onclick = () => this.history(1);
    $('.b-up', this.el).onclick = () => this.up();
    $('.b-star', this.el).onclick = () => this.toggleBookmark();
    const qf = $('.qf', this.el);
    qf.oninput = debounce(() => { this.filter = qf.value; this.apply(); }, 120);
    qf.onkeydown = (e) => { if (e.key === 'Escape') { qf.value = ''; this.filter = ''; this.apply(); this.vl.focus(); } if (e.key === 'ArrowDown') this.vl.focus(); };
    this.vl.addEventListener('scroll', () => this.paint(), { passive: true });
    new ResizeObserver(() => this.paint()).observe(this.vl);
    this.el.addEventListener('mousedown', () => this.fm.activate(this), true);
    this.vl.addEventListener('keydown', (e) => this.key(e));
    this.vl.addEventListener('contextmenu', (e) => {
      if (e.target.closest('.vrow,.tile')) return;
      e.preventDefault();
      this.sel.clear(); this.paint();
      this.fm.menu(e, this, null);
    });
    this.vl.addEventListener('mousedown', (e) => {
      if (e.target === this.vl || e.target === this.inner) { this.sel.clear(); this.paint(); this.fm.preview(this); }
    });
    // Drop target: the pane itself (= current folder) and folder rows.
    this.vl.addEventListener('dragover', (e) => {
      if (!this.path) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = e.ctrlKey || e.altKey || !e.dataTransfer.types.includes('application/x-sg') ? 'copy' : 'move';
      const row = e.target.closest('[data-i]');
      $$('.drop', this.el).forEach((x) => x.classList.remove('drop'));
      const it = row && this.list[+row.dataset.i];
      if (it?.dir) row.classList.add('drop');
    });
    this.vl.addEventListener('dragleave', (e) => { if (!this.vl.contains(e.relatedTarget)) { $$('.drop', this.el).forEach((x) => x.classList.remove('drop')); } });
    this.vl.addEventListener('drop', (e) => {
      e.preventDefault();
      $$('.drop', this.el).forEach((x) => x.classList.remove('drop'));
      const row = e.target.closest('[data-i]');
      const it = row && this.list[+row.dataset.i];
      const dest = it?.dir ? it.path : this.path;
      if (!dest) return;
      const sg = e.dataTransfer.getData('application/x-sg');
      if (sg) {
        const paths = JSON.parse(sg).filter((p) => p !== dest && dirname(p) !== dest);
        if (paths.length) this.fm.transfer(paths, dest, e.ctrlKey || e.altKey);
      } else if (e.dataTransfer.files.length) {
        this.fm.upload(dest, e.dataTransfer);
      }
    });
  }

  async load(path, push = true) {
    try {
      const d = await api('/browse?path=' + encodeURIComponent(path || ''));
      if (push && this.path !== d.path) { this.back.push(this.path); this.fwd = []; }
      const keepSel = this.path === d.path;
      this.path = d.path;
      this.data = d;
      this.entries = d.entries;
      if (!keepSel) { this.sel.clear(); this.focus = -1; this.vl.scrollTop = 0; this.filter = ''; $('.qf', this.el).value = ''; }
      this.apply();
      this.crumbs();
      if (this.fm.active === this) this.fm.syncHash();
    } catch (e) { fail(e); }
  }

  reload() { return this.load(this.path, false); }

  history(d) {
    const from = d < 0 ? this.back : this.fwd;
    const to = d < 0 ? this.fwd : this.back;
    if (!from.length) return;
    to.push(this.path);
    this.load(from.pop(), false);
  }

  up() { if (this.data?.parent != null || this.path) this.load(this.data?.parent ?? '', true); }

  apply() {
    const p = prefs();
    let L = this.entries;
    if (!p.hidden) L = L.filter((e) => !e.hidden);
    if (this.filter) {
      const f = this.filter.toLowerCase();
      if (/[*?]/.test(f)) {
        const rx = new RegExp('^' + f.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$', 'i');
        L = L.filter((e) => rx.test(e.name));
      } else L = L.filter((e) => e.name.toLowerCase().includes(f));
    }
    const k = p.sort, dir = p.dir === 'asc' ? 1 : -1;
    const coll = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
    L = [...L].sort((a, b) => {
      if (a.dir !== b.dir) return a.dir ? -1 : 1;
      let r = 0;
      if (k === 'size') r = (a.size ?? -1) - (b.size ?? -1);
      else if (k === 'mtime') r = a.mtime - b.mtime;
      else if (k === 'ext') r = coll.compare(a.ext, b.ext);
      return (r || coll.compare(a.name, b.name)) * (k === 'name' || r ? dir : 1);
    });
    this.list = L;
    this.listVer = (this.listVer || 0) + 1;
    this.maxSize = Math.max(1, ...L.map((e) => e.size || 0));
    const live = new Set(L.map((e) => e.path));
    for (const s of [...this.sel]) if (!live.has(s)) this.sel.delete(s);
    this.renderHead();
    this.paint();
    this.status();
  }

  crumbs() {
    const c = $('.crumbs', this.el);
    c.innerHTML = '';
    const home = h(`<span class="c">${icon('hdd')}</span>`);
    home.onclick = (e) => { e.stopPropagation(); this.load(''); };
    c.append(home);
    if (this.path) {
      const root = this.data.root_path;
      const parts = this.path.slice(root.length).split('/').filter(Boolean);
      const segs = [[basename(root), root]];
      let acc = root;
      for (const p of parts) { acc += '/' + p; segs.push([p, acc]); }
      for (const [name, path] of segs) {
        c.append(h('<span class="sep">›</span>'));
        const s = h(`<span class="c">${esc(name)}</span>`);
        s.onclick = (e) => { e.stopPropagation(); this.load(path); };
        s.ondragover = (e) => { e.preventDefault(); s.classList.add('drop'); };
        s.ondragleave = () => s.classList.remove('drop');
        s.ondrop = (e) => {
          e.preventDefault(); e.stopPropagation(); s.classList.remove('drop');
          const sg = e.dataTransfer.getData('application/x-sg');
          if (sg) this.fm.transfer(JSON.parse(sg), path, e.ctrlKey || e.altKey);
        };
        c.append(s);
      }
    }
    c.onclick = (e) => {
      if (e.target !== c) return;
      c.innerHTML = `<input value="${esc(this.path)}" spellcheck="false">`;
      const i = $('input', c);
      i.focus(); i.select();
      i.onkeydown = (ev) => { if (ev.key === 'Enter') this.load(i.value.trim()); if (ev.key === 'Escape') this.crumbs(); };
      i.onblur = () => setTimeout(() => this.crumbs(), 150);
    };
    const starred = (state.prefs.bookmarks || []).some((b) => b.path === this.path);
    $('.b-star', this.el).classList.toggle('on', starred);
    $('.b-up', this.el).disabled = !this.path;
    $('.b-back', this.el).disabled = !this.back.length;
    $('.b-fwd', this.el).disabled = !this.fwd.length;
  }

  renderHead() {
    const p = prefs();
    this.head.classList.toggle('hidden', this.mode !== 'list');
    const col = (k, label, right) => `<div data-k="${k}" style="${right ? 'justify-content:flex-end' : ''}">${label}${p.sort === k ? icon(p.dir === 'asc' ? 'up' : 'down') : ''}</div>`;
    this.head.innerHTML = col('name', 'Name') + col('size', 'Size', 1) + col('ext', 'Type') + col('mtime', 'Modified');
    $$('[data-k]', this.head).forEach((d) => (d.onclick = () => {
      const k = d.dataset.k;
      if (p.sort === k) p.dir = p.dir === 'asc' ? 'desc' : 'asc'; else { p.sort = k; p.dir = k === 'name' || k === 'ext' ? 'asc' : 'desc'; }
      savePrefs(); this.fm.panes.forEach((x) => x.apply());
    }));
    $$('svg', this.head).forEach((s) => { s.style.width = '13px'; s.style.height = '13px'; });
  }

  geometry() {
    if (this.mode === 'list') return { cols: 1, rh: compactFiles() ? 48 : ROW, top: 32 };
    const t = prefs().tile;
    const W = this.vl.clientWidth - 16;
    const cols = Math.max(1, Math.floor(W / (t + 10)));
    return { cols, rh: t + 52, top: 8, tw: (W - (cols - 1) * 10) / cols };
  }

  paint() {
    const g = this.geometry();
    const n = this.list.length;
    const rows = Math.ceil(n / g.cols);
    this.nodes ||= new Map();
    const layoutKey = `${this.mode}|${g.cols}|${g.rh}|${n}|${this.listVer}`;
    if (this.layoutKey !== layoutKey) { this.layoutKey = layoutKey; this.nodes.clear(); this.inner.innerHTML = ''; }
    this.inner.style.height = rows * g.rh + (this.mode === 'list' ? 0 : 16) + 'px';
    this.inner.className = 'vl-inner' + (this.mode === 'grid' ? ' tiles' : '');
    if (!n) {
      this.inner.innerHTML = `<div class="empty">${icon(this.filter ? 'search' : 'folderOpen')}<div>${this.filter ? 'No matches' : 'This folder is empty'}</div>
        ${this.path && !this.filter ? '<div class="faint" style="margin-top:6px">Drop files here to upload</div>' : ''}</div>`;
      this.inner.style.height = 'auto';
      this.layoutKey = null;
      return;
    }
    const st = Math.max(0, this.vl.scrollTop - (this.mode === 'list' ? 32 : 0));
    const vh = this.vl.clientHeight;
    const r0 = Math.max(0, Math.floor(st / g.rh) - 4);
    const r1 = Math.min(rows, Math.ceil((st + vh) / g.rh) + 4);
    const cut = state.clipboard?.mode === 'cut' ? new Set(state.clipboard.paths) : null;
    const want = new Set();
    const frag = document.createDocumentFragment();
    for (let r = r0; r < r1; r++) {
      for (let c = 0; c < g.cols; c++) {
        const i = r * g.cols + c;
        if (i >= n) break;
        want.add(i);
        const e = this.list[i];
        const cls = `${this.sel.has(e.path) ? ' sel' : ''}${i === this.focus ? ' focus' : ''}${cut?.has(e.path) ? ' cut' : ''}`;
        let node = this.nodes.get(i);
        if (!node) {
          node = h(this.mode === 'list' ? this.rowHtml(e, i, r, g.rh) : this.tileHtml(e, i, r, c, g));
          this.nodes.set(i, node);
          frag.append(node);
        }
        node.className = (this.mode === 'list' ? 'vrow' : 'tile') + cls;
        if (this.mode === 'grid') { node.style.width = g.tw + 'px'; node.style.left = 8 + c * (g.tw + 10) + 'px'; }
      }
    }
    this.inner.append(frag);
    for (const [i, node] of this.nodes) if (!want.has(i)) { node.remove(); this.nodes.delete(i); }
    this.inner.onmousedown = (ev) => { if (!compactFiles() || this.fm.selecting) this.rowDown(ev); };
    this.inner.onclick = (ev) => { const r = ev.target.closest('[data-i]'); if (r && compactFiles() && !this.fm.selecting) this.open(this.list[+r.dataset.i]); };
    this.inner.ondblclick = (ev) => { const r = ev.target.closest('[data-i]'); if (r && !compactFiles()) this.open(this.list[+r.dataset.i]); };
    this.inner.oncontextmenu = (ev) => {
      const r = ev.target.closest('[data-i]');
      if (!r) return;
      ev.preventDefault();
      const i = +r.dataset.i;
      if (!this.sel.has(this.list[i].path)) { this.sel = new Set([this.list[i].path]); this.focus = i; this.paint(); this.status(); }
      this.fm.menu(ev, this, this.list[i]);
    };
    this.inner.ondragstart = (ev) => {
      const r = ev.target.closest('[data-i]');
      if (!r) return;
      const it = this.list[+r.dataset.i];
      const paths = this.sel.has(it.path) ? [...this.sel] : [it.path];
      ev.dataTransfer.setData('application/x-sg', JSON.stringify(paths));
      ev.dataTransfer.effectAllowed = 'copyMove';
      const ghost = h(`<div style="position:fixed;top:-100px;padding:6px 12px;border-radius:8px;background:var(--accent);color:#fff;font-weight:600">${paths.length} item${paths.length > 1 ? 's' : ''}</div>`);
      document.body.append(ghost);
      ev.dataTransfer.setDragImage(ghost, 10, 10);
      setTimeout(() => ghost.remove(), 0);
    };
  }

  rowHtml(e, i, r, rowHeight) {
    const sz = e.size == null ? '<span class="faint">—</span>' : bytes(e.size);
    const bar = e.dir && e.size ? `<div class="bar-track"><div class="bar-fill" style="width:${(100 * e.size) / this.maxSize}%"></div></div>` : '';
    const type = e.dir ? (e.count != null ? `${num(e.count)} files` : 'Folder') : (e.ext ? e.ext.toUpperCase() : 'File');
    return `<div class="vrow" data-i="${i}" draggable="true" style="top:${r * rowHeight}px;height:${rowHeight - 2}px;grid-template-columns:${COLS}">
      <div class="fname">${fileIcon(e)}<span class="ellipsis">${esc(e.name)}</span></div>
      <div class="szbar num">${bar}<span>${sz}</span></div><div class="muted">${esc(type)}</div>
      <div class="muted num">${e.mtime ? date(e.mtime, true) : ''}</div></div>`;
  }

  tileHtml(e, i, r, c, g) {
    const thumb = !e.dir && THUMBABLE.has(e.ext) ? `<img loading="lazy" alt="" src="${thumbUrl(e, 256)}" data-fallback="icon" data-f='${esc(fileIcon(e, true))}'>` : fileIcon(e, true);
    return `<div class="tile" data-i="${i}" draggable="true" style="top:${g.top + r * g.rh}px;left:${8 + c * (g.tw + 10)}px;width:${g.tw}px;height:${g.rh - 10}px">
      <div class="ck">${icon('check')}</div><div class="th">${thumb}</div>
      <div class="nm" title="${esc(e.name)}">${esc(e.name)}</div>
      <div class="meta">${e.dir ? (e.count != null ? num(e.count) + ' files · ' : '') + bytes(e.size) : bytes(e.size)}</div></div>`;
  }

  rowDown(ev) {
    const r = ev.target.closest('[data-i]');
    if (!r || ev.button === 2) return;
    const i = +r.dataset.i;
    const it = this.list[i];
    const ck = ev.target.closest('.ck');
    if (ev.shiftKey && this.anchor >= 0) {
      const [a, b] = [Math.min(this.anchor, i), Math.max(this.anchor, i)];
      if (!ev.ctrlKey && !ev.metaKey) this.sel.clear();
      for (let k = a; k <= b; k++) this.sel.add(this.list[k].path);
    } else if (ev.ctrlKey || ev.metaKey || ck || (compactFiles() && this.fm.selecting)) {
      this.sel.has(it.path) ? this.sel.delete(it.path) : this.sel.add(it.path);
      this.anchor = i;
    } else if (!this.sel.has(it.path) || this.sel.size === 1) {
      this.sel = new Set([it.path]);
      this.anchor = i;
    } else {
      // Clicking inside a multi-selection keeps it (so it can be dragged); collapse on mouseup without drag.
      const up = () => { this.sel = new Set([it.path]); this.anchor = i; this.paint(); this.status(); };
      r.addEventListener('mouseup', up, { once: true });
      r.addEventListener('dragstart', () => r.removeEventListener('mouseup', up), { once: true });
    }
    this.focus = i;
    this.paint();
    this.status();
    this.fm.preview(this);
  }

  status() {
    const dirs = this.list.filter((e) => e.dir).length;
    const files = this.list.length - dirs;
    const total = this.list.reduce((a, e) => a + (e.dir ? 0 : e.size || 0), 0);
    const sel = this.selected;
    const ssize = sel.reduce((a, e) => a + (e.size || 0), 0);
    const disk = this.data?.disk;
    $('.status', this.el).innerHTML = `<span>${num(dirs)} folders · ${num(files)} files · ${bytes(total)}</span>
      ${sel.length ? `<span style="color:var(--text)"><b>${num(sel.length)}</b> selected · ${bytes(ssize)}</span>` : ''}
      <span class="grow"></span>${disk ? `<span>${bytes(disk.free)} free of ${bytes(disk.total)}</span>` : ''}`;
    this.fm.toolbarState();
  }

  scrollTo(i) {
    const g = this.geometry();
    const top = Math.floor(i / g.cols) * g.rh + (this.mode === 'list' ? 32 : g.top);
    const vh = this.vl.clientHeight;
    if (top < this.vl.scrollTop + (this.mode === 'list' ? 32 : 0)) this.vl.scrollTop = top - (this.mode === 'list' ? 32 : 0);
    else if (top + g.rh > this.vl.scrollTop + vh) this.vl.scrollTop = top + g.rh - vh;
  }

  move(i, ev) {
    i = Math.max(0, Math.min(this.list.length - 1, i));
    if (ev.shiftKey) {
      if (this.anchor < 0) this.anchor = Math.max(this.focus, 0);
      this.sel.clear();
      const [a, b] = [Math.min(this.anchor, i), Math.max(this.anchor, i)];
      for (let k = a; k <= b; k++) this.sel.add(this.list[k].path);
    } else if (!ev.ctrlKey) { this.sel = new Set([this.list[i].path]); this.anchor = i; }
    this.focus = i;
    this.scrollTo(i);
    this.paint();
    this.status();
    this.fm.preview(this);
  }

  key(e) {
    const g = this.geometry();
    const ctrl = e.ctrlKey || e.metaKey;
    const k = e.key;
    const fm = this.fm;
    const stop = () => { e.preventDefault(); e.stopPropagation(); };
    if (k === 'ArrowDown') { stop(); this.move(this.focus + g.cols, e); }
    else if (k === 'ArrowUp') { stop(); this.move(this.focus - g.cols, e); }
    else if (k === 'ArrowRight' && this.mode === 'grid') { stop(); this.move(this.focus + 1, e); }
    else if (k === 'ArrowLeft' && this.mode === 'grid') { stop(); this.move(this.focus - 1, e); }
    else if (k === 'ArrowLeft' && e.altKey) { stop(); this.history(-1); }
    else if (k === 'ArrowRight' && e.altKey) { stop(); this.history(1); }
    else if (k === 'Home') { stop(); this.move(0, e); }
    else if (k === 'End') { stop(); this.move(this.list.length - 1, e); }
    else if (k === 'PageDown') { stop(); this.move(this.focus + Math.floor(this.vl.clientHeight / g.rh) * g.cols, e); }
    else if (k === 'PageUp') { stop(); this.move(this.focus - Math.floor(this.vl.clientHeight / g.rh) * g.cols, e); }
    else if (k === 'Enter') { stop(); if (this.focused) this.open(this.focused); }
    else if (k === 'Backspace') { stop(); this.up(); }
    else if (k === 'Delete') { stop(); fm.remove(this, e.shiftKey); }
    else if (k === 'F2') { stop(); fm.rename(this); }
    else if (k === 'F5' && fm.dual) { stop(); fm.toOther(this, true); }
    else if (k === 'F6' && fm.dual) { stop(); fm.toOther(this, false); }
    else if (k === 'F7') { stop(); fm.mkdir(this); }
    else if (k === 'Tab' && fm.dual) { stop(); fm.activate(fm.panes[1 - this.idx]); fm.panes[1 - this.idx].vl.focus(); }
    else if (ctrl && k.toLowerCase() === 'a') { stop(); this.sel = new Set(this.list.map((x) => x.path)); this.paint(); this.status(); }
    else if (ctrl && k.toLowerCase() === 'i') { stop(); this.invert(); }
    else if (ctrl && k.toLowerCase() === 'c') { stop(); fm.clip(this, 'copy'); }
    else if (ctrl && k.toLowerCase() === 'x') { stop(); fm.clip(this, 'cut'); }
    else if (ctrl && k.toLowerCase() === 'v') { stop(); fm.paste(this); }
    else if (ctrl && k.toLowerCase() === 'f') { stop(); $('.qf', this.el).focus(); }
    else if (k === ' ' && this.focused) { stop(); this.open(this.focused, true); }
    else if (k === 'Escape') { this.sel.clear(); this.paint(); this.status(); }
    else if (k.length === 1 && !ctrl && !e.altKey) {
      // type-ahead: jump to the next name starting with the typed letters
      clearTimeout(this.taT);
      this.ta = (this.ta || '') + k.toLowerCase();
      this.taT = setTimeout(() => (this.ta = ''), 700);
      const start = this.ta.length > 1 ? Math.max(this.focus, 0) : this.focus + 1;
      for (let j = 0; j < this.list.length; j++) {
        const x = (start + j) % this.list.length;
        if (this.list[x].name.toLowerCase().startsWith(this.ta)) { this.move(x, {}); break; }
      }
    }
  }

  invert() {
    this.sel = new Set(this.list.filter((x) => !this.sel.has(x.path)).map((x) => x.path));
    this.paint(); this.status();
  }

  open(it, quick = false) {
    if (it.dir) return this.load(it.path);
    if (MEDIA.has(it.cat) || it.ext === 'pdf') {
      const media = this.list.filter((x) => !x.dir && (MEDIA.has(x.cat) || x.ext === 'pdf'));
      return lightbox(media, Math.max(0, media.indexOf(it)), { onDeleted: () => this.reload() });
    }
    if (quick || TEXT_EXT.has(it.ext)) { prefs().preview = true; this.fm.layout(); return this.fm.preview(this); }
    if (ARCHIVES.test(it.name)) return this.fm.extract(this, it);
    window.open(rawUrl(it), '_blank');
  }

  async toggleBookmark() {
    if (!this.path) return;
    const b = (state.prefs.bookmarks ||= []);
    const i = b.findIndex((x) => x.path === this.path);
    if (i >= 0) b.splice(i, 1); else b.push({ path: this.path, name: basename(this.path) });
    await savePrefs();
    this.crumbs();
    toast(i >= 0 ? 'Bookmark removed' : 'Folder bookmarked — find it in the sidebar', 'info');
  }
}

export function filesView(root, params) {
  const p = prefs();
  const el = h(`<div class="view flush files-view"><h1 class="sr-only">Files</h1><div class="fm">
    <div class="fm-tools">
      <button class="btn sm t-new" title="New folder (F7)">${icon('folderPlus')}New</button>
      <button class="btn sm t-up" title="Upload files or drop them onto the list">${icon('upload')}Upload</button>
      <span style="width:6px"></span>
      <div class="btn-group">
        <button class="btn sm icon t-cut" title="Cut (Ctrl+X)">${icon('scissors')}</button>
        <button class="btn sm icon t-copy" title="Copy (Ctrl+C)">${icon('copy')}</button>
        <button class="btn sm icon t-paste" title="Paste (Ctrl+V)">${icon('clipboard')}</button>
      </div>
      <button class="btn sm t-moveto" title="Move to folder…">${icon('move')}Move to</button>
      <button class="btn sm t-ren" title="Rename (F2) — bulk rename when several are selected">${icon('edit')}Rename</button>
      <button class="btn sm t-zip" title="Compress to .zip">${icon('zip')}Zip</button>
      <button class="btn sm t-dl" title="Download (folders/multiple as .zip)">${icon('download')}</button>
      <button class="btn sm t-del" title="Delete (Del) · Shift+Del = permanent">${icon('trash')}Delete</button>
      <div class="btn-group">
        <button class="btn sm t-sel" title="Selection tools">${icon('selectAll')}Select</button>
      </div>
      <span class="grow"></span>
      <button class="btn sm icon ghost t-hidden" title="Show hidden files">${icon('eye')}</button>
      <div class="seg t-mode"><button data-m="list" title="List" aria-label="List view">${icon('list')}</button><button data-m="grid" title="Thumbnails" aria-label="Thumbnail view">${icon('grid')}</button></div>
      <input type="range" class="t-size" min="100" max="300" step="10" title="Thumbnail size" style="width:90px">
      <button class="btn sm icon t-dual" title="Dual pane (Tab switches, F5 copy / F6 move across)">${icon('columns')}</button>
      <button class="btn sm icon t-prev" title="Preview panel">${icon('panel')}</button>
      <button class="btn sm fm-mobile-more" aria-expanded="false">${icon('down')}More</button>
    </div>
    <div class="fm-body"></div></div>
    <input type="file" multiple class="hidden up-files"><input type="file" multiple webkitdirectory class="hidden up-dir"></div>`);
  root.append(el);
  const toolbar = $('.fm-tools',el);
  [...toolbar.children].forEach(child => { if (!child.matches('.t-new,.t-up,.fm-mobile-more') && !child.querySelector('.t-sel')) child.classList.add('fm-extra'); });
  $('.fm-mobile-more',el).onclick = (e) => { const expanded = toolbar.classList.toggle('expanded'); e.currentTarget.setAttribute('aria-expanded',String(expanded)); e.currentTarget.innerHTML = icon(expanded ? 'up' : 'down') + (expanded ? 'Less' : 'More'); };
  const body = $('.fm-body', el);
  const pv = h('<div class="preview"></div>');

  const fm = {
    selecting: false,
    panes: [],
    active: null,
    get dual() { return prefs().dual; },
    activate(pane) {
      if (this.active === pane) return;
      this.active = pane;
      this.panes.forEach((x) => { x.el.classList.toggle('active-pane', x === pane && this.dual); x.el.classList.toggle('inactive', x !== pane && this.dual); });
      this.toolbarState();
      this.syncHash();
      this.preview(pane);
    },
    syncHash() {
      const want = '#/files' + (this.active?.path ? '?path=' + encodeURIComponent(this.active.path) : '');
      if (location.hash !== want) history.replaceState(null, '', want);
    },
    layout() {
      const pr = prefs();
      body.innerHTML = '';
      if (pr.dual && this.panes.length < 2) {
        const p2 = new Pane(this, 1);
        this.panes.push(p2);
        p2.load(this.panes[0].path, false);
      }
      body.append(this.panes[0].el);
      if (pr.dual) body.append(this.panes[1].el);
      if (pr.preview) body.append(pv);
      $('.t-dual', el).classList.toggle('on', pr.dual);
      $('.t-prev', el).classList.toggle('on', pr.preview);
      $('.t-hidden', el).classList.toggle('on', pr.hidden);
      $('.t-hidden', el).innerHTML = icon(pr.hidden ? 'eye' : 'eyeOff');
      $$('.t-mode button', el).forEach((b) => b.classList.toggle('on', b.dataset.m === pr.mode));
      $('.t-size', el).value = pr.tile;
      $('.t-size', el).classList.toggle('hidden', pr.mode !== 'grid');
      if (!pr.dual) this.activate(this.panes[0]);
      this.panes.forEach((x) => { x.el.classList.toggle('active-pane', x === this.active && pr.dual); x.el.classList.toggle('inactive', x !== this.active && pr.dual); x.apply(); });
      this.preview(this.active);
    },
    toolbarState() {
      const a = this.active;
      if (!a) return;
      const n = a.sel.size;
      const inFolder = !!a.path;
      $('.t-new', el).disabled = !inFolder;
      $('.t-up', el).disabled = !inFolder || !hasFeature('uploads');$('.t-up',el).hidden=!hasFeature('uploads');
      for (const c of ['.t-cut', '.t-copy', '.t-moveto', '.t-ren', '.t-zip', '.t-dl', '.t-del']) $(c, el).disabled = !n || !inFolder;
      $('.t-paste', el).disabled = !state.clipboard || !inFolder;
    },
    targets(pane) { return pane.selected.map((e) => e.path); },
    async transfer(paths, dest, copy) {
      if (!paths.length) return;
      const t = await runTask(api('/move', { paths, dest, copy }));
      if (t) this.refreshAll();
    },
    refreshAll() { this.panes.forEach((x) => x.path !== undefined && x.reload()); emit('fs-changed'); },
    clip(pane, mode) {
      const paths = this.targets(pane);
      if (!paths.length) return;
      state.clipboard = { mode, paths };
      toast(`${paths.length} item${paths.length > 1 ? 's' : ''} ${mode === 'cut' ? 'cut' : 'copied'} — paste with Ctrl+V`, 'info', 2500);
      this.panes.forEach((x) => x.paint());
      this.toolbarState();
    },
    async paste(pane) {
      const c = state.clipboard;
      if (!c || !pane.path) return;
      await this.transfer(c.paths, pane.path, c.mode === 'copy');
      if (c.mode === 'cut') state.clipboard = null;
      this.toolbarState();
    },
    async toOther(pane, copy) {
      const other = this.panes[1 - pane.idx];
      const paths = this.targets(pane);
      if (!paths.length || !other.path) return toast('Open a destination folder in the other pane', 'info');
      if (await confirmBox(copy ? 'Copy' : 'Move', `${copy ? 'Copy' : 'Move'} <b>${paths.length}</b> item(s) to <span class="mono">${esc(shortPath(other.path))}</span>?`, copy ? 'Copy' : 'Move')) this.transfer(paths, other.path, copy);
    },
    async remove(pane, permanent = false) {
      const sel = pane.selected;
      if (!sel.length || !pane.path) return;
      const size = sel.reduce((a, e) => a + (e.size || 0), 0);
      const t = await confirmDelete({ paths: sel.map((e) => e.path), count: sel.length, size, reason: 'file manager',
        extra: permanent ? '<div class="notice danger">' + icon('alert') + '<div>Shift+Delete: tick "Delete permanently" to skip the recycle bin.</div></div>' : '' });
      if (t) this.refreshAll();
    },
    async rename(pane) {
      const sel = pane.selected;
      if (!sel.length) return;
      if (sel.length > 1) return bulkRename(sel, () => this.refreshAll());
      const it = sel[0];
      const n = await prompt('Rename', it.name);
      if (!n || n === it.name) return;
      try { await api('/rename', { path: it.path, name: n }); this.refreshAll(); } catch (e) { fail(e); }
    },
    async mkdir(pane) {
      if (!pane.path) return;
      const n = await prompt('New folder', 'New folder');
      if (!n) return;
      try { await api('/mkdir', { parent: pane.path, name: n }); await pane.reload(); const i = pane.list.findIndex((x) => x.name === n); if (i >= 0) pane.move(i, {}); } catch (e) { fail(e); }
    },
    async zip(pane) {
      const sel = pane.selected;
      if (!sel.length) return;
      const n = await prompt('Compress to .zip', sel.length === 1 ? sel[0].name.replace(/\.[^.]+$/, '') : basename(pane.path) || 'archive', 'Archive name');
      if (!n) return;
      const t = await runTask(api('/compress', { paths: sel.map((e) => e.path), dest: pane.path, name: n }));
      if (t) pane.reload();
    },
    async extract(pane, it) {
      if (!(await confirmBox('Extract archive', `Extract <b>${esc(it.name)}</b> into a new folder next to it?`, 'Extract'))) return;
      const t = await runTask(api('/extract', { path: it.path }));
      if (t) pane.reload();
    },
    download(pane) {
      const sel = pane.selected;
      if (!sel.length) return;
      if (sel.length === 1 && !sel[0].dir) { location.href = rawUrl(sel[0], true); return; }
      const name = sel.length === 1 ? sel[0].name : basename(pane.path) || 'download';
      location.href = `/api/zip?paths=${encodeURIComponent(JSON.stringify(sel.map((e) => e.path)))}&name=${encodeURIComponent(name)}`;
    },
    async moveTo(pane, copy = false) {
      const paths = this.targets(pane);
      if (!paths.length) return;
      const dest = await pickFolder(copy ? 'Copy to…' : 'Move to…', this.panes[1 - pane.idx]?.path || pane.path);
      if (dest) this.transfer(paths, dest, copy);
    },
    async upload(dest, src) {
      if(!hasFeature('uploads')) {toast('Uploads are turned off in Settings → Features.','err');return;}
      const files = [];
      const rel = [];
      // Folder drops: walk the dropped directory entries so the structure is preserved.
      const items = src.items ? [...src.items].map((i) => i.webkitGetAsEntry?.()).filter(Boolean) : null;
      if (items?.some((x) => x.isDirectory)) {
        const walk = (entry, prefix) => new Promise((res) => {
          if (entry.isFile) entry.file((f) => { files.push(f); rel.push(prefix + f.name); res(); });
          else {
            const rd = entry.createReader();
            const all = [];
            const next = () => rd.readEntries(async (batch) => {
              if (!batch.length) { for (const c of all) await walk(c, prefix + entry.name + '/'); res(); } else { all.push(...batch); next(); }
            });
            next();
          }
        });
        for (const it of items) await walk(it, '');
      } else {
        for (const f of src.files) { files.push(f); rel.push(f.webkitRelativePath || f.name); }
      }
      if (!files.length) return;
      const total = files.reduce((a, f) => a + f.size, 0);
      const t = h(`<div class="toast"><div class="spin"></div><div class="grow"><div>Uploading ${num(files.length)} file(s) · ${bytes(total)}</div><div class="progress"><div style="width:0"></div></div></div></div>`);
      let box = $('.toasts'); if (!box) { box = h('<div class="toasts"></div>'); document.body.append(box); }
      box.append(t);
      // Batches of ~200 MB keep each request reasonable.
      let sent = 0;
      try {
        let i = 0;
        while (i < files.length) {
          const fd = new FormData();
          fd.append('dir', dest);
          const rels = [];
          let bsz = 0;
          while (i < files.length && (bsz === 0 || bsz + files[i].size < 200 * 2 ** 20) && rels.length < 500) {
            fd.append('files', files[i], files[i].name); rels.push(rel[i]); bsz += files[i].size; i++;
          }
          fd.append('relpaths', JSON.stringify(rels));
          await new Promise((res, rej) => {
            const x = new XMLHttpRequest();
            x.open('POST', '/api/upload');
            x.upload.onprogress = (ev) => { $('.progress div', t).style.width = `${(100 * (sent + ev.loaded)) / total}%`; };
            x.onload = () => (x.status < 300 ? res() : rej(new Error(x.responseText)));
            x.onerror = () => rej(new Error('upload failed'));
            x.send(fd);
          });
          sent += bsz;
        }
        t.remove();
        toast(`Uploaded <b>${num(files.length)}</b> file(s)`);
      } catch (e) { t.remove(); fail(e); }
      this.refreshAll();
    },
    menu(ev, pane, it) {
      const sel = pane.selected;
      const n = sel.length;
      const inFolder = !!pane.path;
      const items = it ? [
        { label: it.dir ? 'Open' : 'Open / preview', icon: it.dir ? 'folderOpen' : 'eye', key: 'Enter', run: () => pane.open(it) },
        it.dir && this.dual ? { label: 'Open in other pane', icon: 'columns', run: () => this.panes[1 - pane.idx].load(it.path) } : null,
        !it.dir ? { label: 'Open in new tab', icon: 'expand', run: () => window.open(rawUrl(it), '_blank') } : null,
        { label: n > 1 ? `Download ${n} as .zip` : it.dir ? 'Download as .zip' : 'Download', icon: 'download', run: () => this.download(pane) },
        '-',
        { label: 'Cut', icon: 'scissors', key: 'Ctrl+X', run: () => this.clip(pane, 'cut') },
        { label: 'Copy', icon: 'copy', key: 'Ctrl+C', run: () => this.clip(pane, 'copy') },
        { label: 'Paste into folder', icon: 'clipboard', disabled: !state.clipboard || !it.dir, run: () => this.transfer(state.clipboard.paths, it.path, state.clipboard.mode === 'copy') },
        { label: 'Move to…', icon: 'move', run: () => this.moveTo(pane) },
        { label: 'Copy to…', icon: 'copy', run: () => this.moveTo(pane, true) },
        this.dual ? { label: 'Copy to other pane', icon: 'columns', key: 'F5', run: () => this.toOther(pane, true) } : null,
        this.dual ? { label: 'Move to other pane', icon: 'columns', key: 'F6', run: () => this.toOther(pane, false) } : null,
        '-',
        { label: n > 1 ? `Bulk rename ${n} items…` : 'Rename', icon: 'edit', key: 'F2', run: () => this.rename(pane) },
        { label: 'Compress to .zip', icon: 'zip', run: () => this.zip(pane) },
        !it.dir && ARCHIVES.test(it.name) ? { label: 'Extract here', icon: 'archive', run: () => this.extract(pane, it) } : null,
        !it.dir ? { label: `Select all .${it.ext || '(no ext)'} here`, icon: 'selectAll', run: () => { pane.sel = new Set(pane.list.filter((x) => !x.dir && x.ext === it.ext).map((x) => x.path)); pane.paint(); pane.status(); } } : null,
        it.dir ? { label: 'Analyze folder size', icon: 'pie', run: () => { pane.focus = pane.list.indexOf(it); prefs().preview = true; this.layout(); } } : null,
        { label: 'Properties', icon: 'info', run: () => properties(it) },
        '-',
        { label: n > 1 ? `Delete ${n} items` : 'Delete', icon: 'trash', key: 'Del', danger: true, run: () => this.remove(pane) },
      ] : [
        { label: 'New folder', icon: 'folderPlus', key: 'F7', disabled: !inFolder, run: () => this.mkdir(pane) },
        { label: 'Upload files…', icon: 'upload', disabled: !inFolder || !hasFeature('uploads'), run: () => $('.up-files', el).click() },
        { label: 'Upload folder…', icon: 'upload', disabled: !inFolder || !hasFeature('uploads'), run: () => $('.up-dir', el).click() },
        { label: 'Paste', icon: 'clipboard', key: 'Ctrl+V', disabled: !state.clipboard || !inFolder, run: () => this.paste(pane) },
        '-',
        { label: 'Select all', icon: 'selectAll', key: 'Ctrl+A', run: () => { pane.sel = new Set(pane.list.map((x) => x.path)); pane.paint(); pane.status(); } },
        { label: 'Select by pattern…', icon: 'filter', run: () => selectPattern(pane) },
        { label: 'Refresh', icon: 'refresh', run: () => pane.reload() },
        { label: 'Search inside this folder', icon: 'search', disabled: !inFolder, run: () => (location.hash = '#/search?dir=' + encodeURIComponent(pane.path)) },
      ];
      contextMenu(ev.clientX, ev.clientY, items);
    },
    preview: debounce(async (pane) => {
      if (!prefs().preview || !pane) return;
      const it = pane.focused && pane.sel.has(pane.focused.path) ? pane.focused : pane.sel.size === 1 ? pane.selected[0] : null;
      const sel = pane.selected;
      if (!it) {
        const target = sel.length ? null : { name: pane.path ? basename(pane.path) : 'All volumes', path: pane.path, dir: true };
        if (sel.length > 1) {
          const size = sel.reduce((a, e) => a + (e.size || 0), 0);
          const byExt = {};
          for (const e of sel) byExt[e.dir ? 'folders' : e.ext || 'other'] = (byExt[e.dir ? 'folders' : e.ext || 'other'] || 0) + (e.size || 0);
          pv.innerHTML = `<div class="pv-info"><h3 style="margin:0">${num(sel.length)} items selected</h3><div class="muted">${bytes(size)} total</div><div class="bars"></div></div>`;
          $('.bars', pv).append(hbars(Object.entries(byExt).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => ({ label: k, value: v })), { fmt: bytes }));
          return;
        }
        return folderInsight(pv, target, pane);
      }
      if (it.dir) return folderInsight(pv, it, pane);
      let media = '';
      if (it.cat === 'image' && THUMBABLE.has(it.ext)) media = `<div class="pv-media"><img alt="${esc(it.name)}" src="${thumbUrl(it, 512)}" data-fallback="remove"></div>`;
      else if (it.cat === 'video') media = `<div class="pv-media"><video src="${rawUrl(it)}" poster="${THUMBABLE.has(it.ext) ? thumbUrl(it, 512) : ''}" controls preload="none"></video></div>`;
      else if (it.cat === 'audio') media = `<div style="padding:16px"><audio src="${rawUrl(it)}" controls style="width:100%"></audio></div>`;
      else if (it.ext === 'pdf') media = `<iframe src="${rawUrl(it)}" style="width:100%;height:420px;border:0;background:#fff"></iframe>`;
      else if (TEXT_EXT.has(it.ext) || (!it.ext && it.size < 65536)) media = '<pre class="txt">Loading…</pre>';
      else media = `<div class="pv-media" style="background:var(--panel2)">${fileIcon(it, true).replace('big-ic', 'big-ic" style="width:96px;height:96px')}</div>`;
      pv.innerHTML = `${media}<div class="pv-info"><div style="font-weight:600;word-break:break-all">${esc(it.name)}</div><div class="kv info-kv">
        <div>Size</div><div>${bytes(it.size)}</div><div>Modified</div><div>${date(it.mtime, true)}</div><div>Type</div><div>${esc(it.ext ? it.ext.toUpperCase() : 'File')}</div></div>
        <div class="row wrap"><a class="btn sm" href="${rawUrl(it, true)}">${icon('download')}Download</a><button class="btn sm props">${icon('info')}Details & checksum</button></div></div>`;
      $('.props', pv).onclick = () => properties(it);
      if ($('.txt', pv)) api('/text?path=' + encodeURIComponent(it.path) + '&limit=65536').then((t) => { const pre = $('.txt', pv); if (pre) pre.textContent = t; }).catch(() => {});
      try {
        const d = await api('/info?path=' + encodeURIComponent(it.path));
        const kv = $('.info-kv', pv);
        if (!kv) return;
        if (d.width) kv.insertAdjacentHTML('beforeend', `<div>Dimensions</div><div>${d.width} × ${d.height}</div>`);
        if (d.taken && Math.abs(d.taken - d.mtime) > 60) kv.insertAdjacentHTML('beforeend', `<div>Taken</div><div>${date(d.taken, true)}</div>`);
        if (d.sharpness != null) kv.insertAdjacentHTML('beforeend', `<div>Sharpness</div><div>${d.sharpness.toFixed(0)} ${d.sharpness < 40 ? '<span class="badge warn">blurry</span>' : ''}</div>`);
        if (d.copies?.length) kv.insertAdjacentHTML('beforeend', `<div>Duplicates</div><div><span class="badge danger">${d.copies.length} other cop${d.copies.length > 1 ? 'ies' : 'y'}</span>${d.copies.slice(0, 5).map((c) => `<div class="mono faint" style="margin-top:4px">${esc(shortPath(c))}</div>`).join('')}</div>`);
      } catch { /* not indexed yet */ }
    }, 120),
  };

  async function folderInsight(pane_el, it, pane) {
    if (!it?.path) {
      const vols = pane.list.filter((e) => e.disk);
      pane_el.innerHTML = `<div class="pv-info"><h3 style="margin:0">Volumes</h3>${vols.map((v) => `<div style="margin-top:10px"><div class="row"><b class="grow">${esc(v.name)}</b><span class="muted">${bytes(v.disk.used)} / ${bytes(v.disk.total)}</span></div>
        <div class="progress"><div style="width:${(100 * v.disk.used) / v.disk.total}%"></div></div><div class="faint" style="font-size:12px;margin-top:4px">${bytes(v.disk.free)} free · ${num(v.count)} files indexed</div></div>`).join('')}</div>`;
      return;
    }
    pane_el.innerHTML = `<div class="pv-info"><div class="row">${fileIcon({ dir: true, cat: 'folder' })}<b class="grow ellipsis">${esc(it.name)}</b></div>
      <div class="kv"><div>Size</div><div class="fsz">…</div><div>Files</div><div class="fct">…</div></div>
      <div class="muted" style="margin-top:6px;font-size:12px;text-transform:uppercase;letter-spacing:.6px">Biggest sub-folders</div><div class="bars"></div>
      <div class="row wrap" style="margin-top:6px"><a class="btn sm" href="#/search?dir=${encodeURIComponent(it.path)}&sort=size">${icon('search')}Largest files inside</a>
      <a class="btn sm" href="#/duplicates?dir=${encodeURIComponent(it.path)}">${icon('copy')}Duplicates inside</a></div></div>`;
    try {
      const [info, kids] = await Promise.all([api('/info?path=' + encodeURIComponent(it.path)), api('/folders?path=' + encodeURIComponent(it.path))]);
      $('.fsz', pane_el).textContent = bytes(info.size);
      $('.fct', pane_el).textContent = num(info.count) + (info.ndirs != null ? ` · ${num(info.ndirs)} sub-folders` : '');
      const bars = $('.bars', pane_el);
      if (!kids.length) bars.innerHTML = '<div class="faint">No sub-folders</div>';
      else bars.append(hbars(kids.slice(0, 12).map((k) => ({ label: basename(k.path), value: k.size, sub: num(k.count) + ' files', onClick: () => pane.load(k.path) })), { fmt: bytes }));
    } catch { $('.fsz', pane_el).textContent = 'not indexed yet'; }
  }

  // Toolbar wiring
  const A = () => fm.active;
  $('.t-new', el).onclick = () => fm.mkdir(A());
  $('.t-up', el).onclick = (e) => contextMenu(e.clientX, e.clientY + 10, [
    { label: 'Upload files…', icon: 'upload', disabled: !hasFeature('uploads'), run: () => $('.up-files', el).click() },
    { label: 'Upload a folder…', icon: 'folderOpen', disabled: !hasFeature('uploads'), run: () => $('.up-dir', el).click() },
  ]);
  $('.up-files', el).onchange = (e) => { fm.upload(A().path, e.target); e.target.value = ''; };
  $('.up-dir', el).onchange = (e) => { fm.upload(A().path, e.target); e.target.value = ''; };
  $('.t-cut', el).onclick = () => fm.clip(A(), 'cut');
  $('.t-copy', el).onclick = () => fm.clip(A(), 'copy');
  $('.t-paste', el).onclick = () => fm.paste(A());
  $('.t-moveto', el).onclick = () => fm.moveTo(A());
  $('.t-ren', el).onclick = () => fm.rename(A());
  $('.t-zip', el).onclick = () => fm.zip(A());
  $('.t-dl', el).onclick = () => fm.download(A());
  $('.t-del', el).onclick = () => fm.remove(A());
  $('.t-sel', el).onclick = (e) => {
    if (compactFiles()) {
      fm.selecting = !fm.selecting;
      e.currentTarget.innerHTML = icon(fm.selecting ? 'check' : 'selectAll') + (fm.selecting ? 'Done' : 'Select');
      e.currentTarget.setAttribute('aria-pressed',String(fm.selecting));
      if (!fm.selecting) fm.panes.forEach(pane => { pane.sel.clear(); pane.paint(); pane.status(); });
      return;
    }
    const pane = A();
    const exts = [...new Set(pane.list.filter((x) => !x.dir).map((x) => x.ext))].slice(0, 8);
    contextMenu(e.clientX, e.clientY + 10, [
      { label: 'Select all', icon: 'selectAll', key: 'Ctrl+A', run: () => { pane.sel = new Set(pane.list.map((x) => x.path)); pane.paint(); pane.status(); } },
      { label: 'Select none', icon: 'x', key: 'Esc', run: () => { pane.sel.clear(); pane.paint(); pane.status(); } },
      { label: 'Invert selection', icon: 'invert', key: 'Ctrl+I', run: () => pane.invert() },
      { label: 'Select by pattern…', icon: 'filter', run: () => selectPattern(pane) },
      { label: 'Select files only', icon: 'file', run: () => { pane.sel = new Set(pane.list.filter((x) => !x.dir).map((x) => x.path)); pane.paint(); pane.status(); } },
      { label: 'Select files larger than…', icon: 'filter', run: () => selectLarger(pane) },
      '-',
      ...exts.map((x) => ({ label: `All .${x || '(none)'}`, icon: 'file', run: () => { pane.sel = new Set(pane.list.filter((y) => !y.dir && y.ext === x).map((y) => y.path)); pane.paint(); pane.status(); } })),
    ]);
  };
  $('.t-hidden', el).onclick = () => { prefs().hidden = !prefs().hidden; savePrefs(); fm.layout(); };
  $$('.t-mode button', el).forEach((b) => (b.onclick = () => { prefs().mode = b.dataset.m; savePrefs(); fm.layout(); }));
  $('.t-size', el).oninput = (e) => { prefs().tile = +e.target.value; fm.panes.forEach((x) => x.paint()); };
  $('.t-size', el).onchange = () => savePrefs();
  $('.t-dual', el).onclick = () => { prefs().dual = !prefs().dual; savePrefs(); fm.layout(); };
  $('.t-prev', el).onclick = () => { prefs().preview = !prefs().preview; savePrefs(); fm.layout(); };

  const p1 = new Pane(fm, 0);
  fm.panes.push(p1);
  fm.active = p1;
  fm.layout();
  p1.load(params.get('path') || '', false).then(() => p1.vl.focus());
  const off = on('changed', () => fm.panes.forEach((x) => x.reload()));
  const offPrefs = on('prefs', () => fm.panes.forEach((x) => x.crumbs()));
  return () => { off(); offPrefs(); closeContext(); };
}

async function selectPattern(pane) {
  const v = await prompt('Select by pattern', '*.jpg', 'Wildcards: * any text, ? one character. Separate several with ;');
  if (!v) return;
  const rxs = v.split(';').map((s) => s.trim()).filter(Boolean).map((s) => new RegExp('^' + s.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$', 'i'));
  pane.sel = new Set(pane.list.filter((x) => rxs.some((r) => r.test(x.name))).map((x) => x.path));
  pane.paint(); pane.status();
  toast(`${pane.sel.size} items selected`, 'info', 2000);
}

async function selectLarger(pane) {
  const v = await prompt('Select files larger than', '100 MB', 'e.g. 500 KB, 100 MB, 2 GB');
  if (!v) return;
  const m = v.trim().toLowerCase().match(/^([\d.]+)\s*(b|kb|mb|gb|tb)?$/);
  if (!m) return toast('Could not read that size', 'err');
  const n = parseFloat(m[1]) * { b: 1, kb: 1024, mb: 2 ** 20, gb: 2 ** 30, tb: 2 ** 40 }[m[2] || 'mb'];
  pane.sel = new Set(pane.list.filter((x) => !x.dir && x.size > n).map((x) => x.path));
  pane.paint(); pane.status();
}

async function properties(it) {
  const body = h('<div class="muted">Loading…</div>');
  modal({ title: it.name, body, icon: it.dir ? 'folder' : 'info', actions: [{ label: 'Close', value: null }] });
  try {
    const d = await api('/info?path=' + encodeURIComponent(it.path));
    body.className = '';
    body.innerHTML = `<div class="kv">
      <div>Location</div><div class="mono">${esc(d.path)}</div>
      <div>Size</div><div>${bytes(d.size)} <span class="faint">(${num(d.size)} bytes)</span></div>
      ${d.dir ? `<div>Contains</div><div>${num(d.count)} files · ${num(d.ndirs)} folders</div>` : `<div>Type</div><div>${esc(d.mime || 'unknown')}</div>`}
      <div>Modified</div><div>${date(d.mtime, true)}</div><div>Changed</div><div>${date(d.ctime, true)}</div>
      <div>Permissions</div><div class="mono">${d.mode} · uid ${d.uid} · gid ${d.gid}</div>
      ${d.width ? `<div>Dimensions</div><div>${d.width} × ${d.height}</div>` : ''}
      ${d.taken ? `<div>Taken</div><div>${date(d.taken, true)}</div>` : ''}
      ${!d.dir ? `<div>Checksum</div><div class="mono hash">${d.hash ? esc(d.hash) : '<button class="btn sm calc">Compute BLAKE2 checksum</button>'}</div>` : ''}
      ${d.copies?.length ? `<div>Duplicates</div><div>${d.copies.map((c) => `<div class="mono">${esc(c)}</div>`).join('')}</div>` : ''}
    </div>`;
    const calc = $('.calc', body);
    if (calc) calc.onclick = async () => { calc.disabled = true; calc.textContent = 'Hashing…'; const r = await api('/info?hash=1&path=' + encodeURIComponent(it.path)); $('.hash', body).textContent = r.hash || 'unreadable'; };
  } catch (e) { body.textContent = e.message; }
}

export async function bulkRename(items, done) {
  const body = h(`<div class="col" style="gap:12px">
    <div class="seg mode"><button data-m="text" class="on">Find & replace</button><button data-m="regex">Regex</button><button data-m="template">Pattern / numbering</button></div>
    <div class="row f-text"><input class="input grow find" placeholder="Find"><input class="input grow repl" placeholder="Replace with"></div>
    <div class="row f-tpl hidden"><input class="input grow tpl" value="{name}_{n:3}"><input class="input start" type="number" value="1" style="width:80px" title="Start number"></div>
    <div class="faint f-help" style="font-size:12px">Plain text replace in the full name.</div>
    <div class="row"><span class="muted">Case:</span><div class="seg case"><button data-c="" class="on">Keep</button><button data-c="lower">lower</button><button data-c="upper">UPPER</button><button data-c="title">Title</button></div></div>
    <div style="max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:10px"><table class="tbl"><thead><tr><th>Current name</th><th>New name</th></tr></thead><tbody></tbody></table></div>
  </div>`);
  let mode = 'text', kase = '', plan = [];
  const help = { text: 'Plain text replace in the full name.', regex: 'JavaScript-style regex on the full name, Python syntax for groups: \\1 or \\g<1>.', template: 'Tokens: {name} original name · {n} counter · {n:3} zero-padded (001) · {date} modified date · {ext} extension.' };
  const refresh = debounce(async () => {
    try {
      const r = await api('/rename/preview', {
        paths: items.map((x) => x.path), mode, case: kase || null, start: +$('.start', body).value || 1,
        find: $('.find', body).value, replace: mode === 'template' ? $('.tpl', body).value : $('.repl', body).value,
      });
      plan = r.items;
      $('tbody', body).innerHTML = r.items.map((x) => `<tr><td class="mono">${esc(x.old)}</td><td class="mono ${x.clash ? 'danger-text' : x.new !== x.old ? 'ok-text' : 'faint'}">${esc(x.new)}${x.clash ? ' (duplicate!)' : ''}</td></tr>`).join('');
    } catch (e) { $('tbody', body).innerHTML = `<tr><td colspan="2" class="danger-text">${esc(e.message)}</td></tr>`; }
  }, 200);
  $$('.mode button', body).forEach((b) => (b.onclick = () => {
    mode = b.dataset.m;
    $$('.mode button', body).forEach((x) => x.classList.toggle('on', x === b));
    $('.f-text', body).classList.toggle('hidden', mode === 'template');
    $('.f-tpl', body).classList.toggle('hidden', mode !== 'template');
    $('.f-help', body).textContent = help[mode];
    refresh();
  }));
  $$('.case button', body).forEach((b) => (b.onclick = () => { kase = b.dataset.c; $$('.case button', body).forEach((x) => x.classList.toggle('on', x === b)); refresh(); }));
  $$('input', body).forEach((i) => (i.oninput = refresh));
  refresh();
  const ok = await modal({ title: `Bulk rename ${items.length} items`, body, wide: true, icon: 'edit',
    actions: [{ label: 'Cancel', value: false }, { label: 'Rename all', cls: 'primary', value: true, validate: () => (plan.some((x) => x.clash) ? (toast('Fix duplicate names first', 'err'), false) : true) }] });
  if (!ok) return;
  const changes = plan.filter((x) => x.new !== x.old);
  if (!changes.length) return;
  const t = await runTask(api('/rename/bulk', { items: changes }));
  if (t) done?.();
}
