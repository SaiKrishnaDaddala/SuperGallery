import { $, ago, api, basename, bytes, CAT_COLORS, CAT_LABEL, esc, fail, h, icon, num, on, shortPath, state } from '../core.js';
import { scopeBanner } from './categories.js';
import { columns, donut, hbars, PALETTE, treemap } from '../charts.js';

const KIND_COLOR = { dupes: '#ff3b30', similar: '#af52de', chat: '#34c759', web: '#ff9500', cache: '#8e8e93', phonetrash: '#ff9500', screenshot: '#5ac8fa', lowq: '#ffcc00', blurry: '#5856d6', dark: '#3a3a3c', screenrec: '#ff2d55', junk: '#8e8e93', temp: '#ff9500', empty: '#8e8e93', old_large: '#a2845e', installers: '#30b0c7', empty_folders: '#1e9bff', info: '#007aff', learned: '#5856d6' };
const KIND_ICON = { dupes: 'copy', similar: 'layers', junk: 'broom', temp: 'hourglass', empty: 'file', blurry: 'blur', old_large: 'archive', installers: 'package', dark: 'moon', empty_folders: 'folder', info: 'pie', chat: 'sparkles', web: 'download', cache: 'broom', phonetrash: 'trash', screenshot: 'monitor', lowq: 'minimize', screenrec: 'video' };

export function dashboardView(root) {
  const el = h(`<div class="view"><div class="page-head"><div class="grow"><h1>Storage insights</h1><p class="sub">Loading your NAS…</p></div>
    <button class="btn rescan">${icon('refresh')}Rescan</button></div>${scopeBanner()}<div class="body"></div></div>`);
  root.append(el);
  $('.rescan', el).onclick = () => api('/scan', {}).catch(fail);

  async function load() {
    let s, tips;
    let learned = [];
    try { [s, tips, learned] = await Promise.all([api('/stats'), api('/insights'), api('/learned').catch(() => [])]); } catch (e) { return fail(e); }
    const st = state.status || {};
    const reviewCount = tips.filter((t) => t.kind !== 'info').length;
    $('.sub', el).innerHTML = s.total_files ? `${num(s.total_files)} files indexed across ${s.roots.length} volume${s.roots.length > 1 ? 's' : ''} · last scan ${ago(s.last_scan)}${s.photos_pending ? ` · <span class="badge accent">analyzing ${num(s.photos_pending)} photos</span>` : ''}`
      : 'The first scan is running — results appear here as soon as it finishes.';
    const b = $('.body', el);
    b.innerHTML = '';
    b.append(h(`<div class="grid g4" style="margin-bottom:16px">
      <div class="card kpi"><div class="ic">${icon('file')}</div><div><div class="v">${num(s.total_files)}</div><div class="l">files · avg ${bytes(s.avg_size)}</div></div></div>
      <div class="card kpi"><div class="ic green">${icon('hdd')}</div><div><div class="v">${bytes(s.total_size)}</div><div class="l">total indexed size</div></div></div>
      <a class="card kpi" href="#/duplicates" style="color:inherit"><div class="ic red">${icon('copy')}</div><div><div class="v">${bytes(s.dupes.wasted)}</div><div class="l">${num(s.dupes.extra_files)} duplicate copies</div></div></a>
      <a class="card kpi" href="#/categories" style="color:inherit"><div class="ic purple">${icon('sparkles')}</div><div><div class="v">${num(reviewCount)}</div><div class="l">suggestions to review</div></div></a></div>`));

    const g = h('<div class="grid g3"></div>');
    b.append(g);

    // Smart assistant
    const ins = h(`<div class="card span2"><h3>Suggestions<span class="right muted">largest savings first</span></h3><div class="list"></div></div>`);
    const list = $('.list', ins);
    if (!tips.length) list.innerHTML = `<div class="empty" style="padding:30px">${icon('check')}<div>Your NAS looks clean. Nothing to suggest right now.</div></div>`;
    for (const t of tips.slice(0, 8)) {
      list.append(h(`<a class="insight" href="${t.view}" style="color:inherit"><div class="ic" style="background:${KIND_COLOR[t.kind] || '#007aff'}">${icon(KIND_ICON[t.kind] || 'zap')}</div>
        <div class="grow"><div class="t">${esc(t.title)}</div><div class="d">${esc(t.text)}</div></div>
        ${t.size ? `<div class="s">${bytes(t.size)}</div>` : ''}<span class="faint">${icon('right')}</span></a>`));
    }
    g.append(ins);

    // Volumes
    const vols = h(`<div class="card"><h3>${icon('hdd')}Storage</h3><div class="col vlist" style="gap:14px"></div></div>`);
    api('/browse?path=').then((d) => {
      for (const v of d.entries) {
        const du = v.disk;
        $('.vlist', vols).append(h(`<a href="#/files?path=${encodeURIComponent(v.path)}" style="color:inherit"><div class="row"><b class="grow">${esc(v.name)}</b>
          <span class="muted num">${du ? `${bytes(du.used)} / ${bytes(du.total)}` : bytes(v.size)}</span></div>
          ${du ? `<div class="progress" style="height:9px"><div style="width:${(100 * du.used) / du.total}%;${du.used / du.total > 0.9 ? 'background:var(--danger)' : ''}"></div></div>
          <div class="faint" style="font-size:12px;margin-top:5px">${bytes(du.free)} free · ${num(v.count)} files indexed (${bytes(v.size)})</div>` : ''}</a>`));
      }
    }).catch(() => {});
    g.append(vols);

    // Learned from previous deletions
    if (learned.length) {
      const lc = h(`<div class="card span2"><h3>Based on your past cleanups</h3><div class="list"></div></div>`);
      for (const t of learned) {
        $('.list', lc).append(h(`<a class="insight learned" href="${t.view}" style="color:inherit"><div class="ic">${icon(t.icon || 'zap')}</div>
          <div class="grow"><div class="t">${esc(t.title)}</div><div class="d">${esc(t.text)}</div></div>
          <div class="s">${bytes(t.size)}</div><span class="faint">${icon('right')}</span></a>`));
      }
      g.append(lc);
    }


    // By category
    const cats = s.by_cat.map((c) => ({ label: CAT_LABEL[c.cat] || c.cat, value: c.size, color: CAT_COLORS[c.cat], sub: `${num(c.count)} files`, onClick: () => (location.hash = `#/search?cat=${c.cat}&sort=size`) }));
    const cc = h(`<div class="card"><h3>${icon('pie')}Space by type</h3></div>`);
    cc.append(donut(cats, { center: bytes(s.total_size), centerSub: 'total', fmt: bytes }));
    g.append(cc);

    // By extension: toggle size/count
    const ext = h(`<div class="card"><h3>${icon('bars')}Top file extensions<span class="right"><span class="seg"><button class="on" data-m="size">Size</button><button data-m="count">Count</button></span></span></h3><div class="c"></div>
      <a href="#/extensions" class="btn sm ghost" style="margin-top:10px">All file types ${icon('right')}</a></div>`);
    const drawExt = (m) => {
      const arr = [...s.by_ext].sort((a, b2) => b2[m] - a[m]).slice(0, 10);
      $('.c', ext).innerHTML = '';
      $('.c', ext).append(hbars(arr.map((x) => ({ label: x.ext ? '.' + x.ext : '(no extension)', value: x[m], sub: m === 'size' ? `${num(x.count)} files` : bytes(x.size), color: CAT_COLORS[x.cat], onClick: () => (location.hash = `#/search?ext=${x.ext}&sort=size`) })), { fmt: m === 'size' ? bytes : num }));
    };
    ext.querySelectorAll('.seg button').forEach((bt) => (bt.onclick = () => { ext.querySelectorAll('.seg button').forEach((x) => x.classList.toggle('on', x === bt)); drawExt(bt.dataset.m); }));
    drawExt('size');
    g.append(ext);

    // Size distribution
    const hist = h(`<div class="card"><h3>${icon('bars')}File size distribution<span class="right"><span class="seg"><button class="on" data-m="count">Count</button><button data-m="size">Space</button></span></span></h3><div class="c"></div></div>`);
    const drawHist = (m) => {
      $('.c', hist).innerHTML = '';
      $('.c', hist).append(columns(s.size_hist.map((x) => ({ label: x.label, value: x[m], tipHtml: `<b>${x.label}</b><br>${num(x.count)} files · ${bytes(x.size)}` })), { fmt: m === 'size' ? bytes : num }));
    };
    hist.querySelectorAll('.seg button').forEach((bt) => (bt.onclick = () => { hist.querySelectorAll('.seg button').forEach((x) => x.classList.toggle('on', x === bt)); drawHist(bt.dataset.m); }));
    drawHist('count');
    g.append(hist);

    // Treemap of top level folders
    const tm = h(`<div class="card span2"><h3>${icon('grid')}Where your space goes<span class="right muted">top-level folders · click to open</span></h3></div>`);
    tm.append(treemap(s.top_level.map((f, i) => ({ label: basename(f.path), value: f.size, sub: `${num(f.count)} files`, color: PALETTE[i % PALETTE.length], onClick: () => (location.hash = '#/files?path=' + encodeURIComponent(f.path)) })), { fmt: bytes, height: 300 }));
    g.append(tm);

    // Files by year
    const yr = h(`<div class="card"><h3>${icon('calendar')}Files by year<span class="right"><span class="seg"><button class="on" data-m="size">Space</button><button data-m="count">Count</button></span></span></h3><div class="c"></div></div>`);
    const years = s.by_year.filter((y) => y.year > 1990);
    const drawYear = (m) => {
      $('.c', yr).innerHTML = '';
      $('.c', yr).append(columns(years.slice(-14).map((y) => ({ label: `'${String(y.year).slice(2)}`, value: y[m], tipHtml: `<b>${y.year}</b><br>${num(y.count)} files · ${bytes(y.size)}`, onClick: () => (location.hash = `#/search?year=${y.year}&sort=size`) })), { fmt: m === 'size' ? bytes : num }));
    };
    yr.querySelectorAll('.seg button').forEach((bt) => (bt.onclick = () => { yr.querySelectorAll('.seg button').forEach((x) => x.classList.toggle('on', x === bt)); drawYear(bt.dataset.m); }));
    drawYear('size');
    g.append(yr);

    // Largest files
    const lf = h(`<div class="card span2"><h3>${icon('hdd')}Largest files<span class="right"><a href="#/large" class="btn sm ghost">See all ${icon('right')}</a></span></h3><div></div></div>`);
    const lfl = lf.lastElementChild;
    for (const f of s.largest.slice(0, 10)) {
      lfl.append(h(`<a class="list-row" style="color:inherit" href="#/files?path=${encodeURIComponent(f.dir)}"><span class="badge" style="background:${CAT_COLORS[f.cat]}22;color:${CAT_COLORS[f.cat]}">${esc(f.ext || '—')}</span>
        <span class="grow ellipsis">${esc(f.name)}</span><span class="faint ellipsis mono" style="max-width:40%">${esc(shortPath(f.dir))}</span><b class="num">${bytes(f.size)}</b></a>`));
    }
    g.append(lf);

    // Largest folders
    const tf = h(`<div class="card"><h3>${icon('folder')}Largest folders</h3></div>`);
    tf.append(hbars(s.top_folders.slice(0, 10).map((f) => ({ label: shortPath(f.path), value: f.size, sub: `${num(f.count)} files`, onClick: () => (location.hash = '#/files?path=' + encodeURIComponent(f.path)) })), { fmt: bytes }));
    g.append(tf);
  }
  load();
  const off = on('changed', load);
  return off;
}
