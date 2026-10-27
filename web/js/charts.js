// Dependency-free SVG/HTML charts: donut, horizontal bars, columns, treemap.
import { esc, h, tip } from './core.js';

export const PALETTE = ['#007aff', '#34c759', '#ff9500', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00', '#5856d6', '#ff3b30', '#30b0c7', '#a2845e', '#8e8e93'];

/** data: [{label, value, color?, onClick?, sub?}] */
export function donut(data, { size = 190, thickness = 26, center = '', centerSub = '', fmt = String } = {}) {
  const total = data.reduce((a, d) => a + d.value, 0) || 1;
  const r = size / 2 - thickness / 2 - 2;
  const C = 2 * Math.PI * r;
  let off = 0;
  const segs = data.map((d, i) => {
    const len = (d.value / total) * C;
    const s = `<circle data-i="${i}" r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="${d.color || PALETTE[i % PALETTE.length]}"
      stroke-width="${thickness}" stroke-dasharray="${Math.max(len - 1.5, 0.01)} ${C}" stroke-dashoffset="${-off}" style="cursor:pointer;transition:stroke-width .15s"
      transform="rotate(-90 ${size / 2} ${size / 2})"/>`;
    off += len;
    return s;
  }).join('');
  const el = h(`<div class="row" style="gap:22px;align-items:center;flex-wrap:wrap">
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="flex:none">${segs}
      <text x="50%" y="48%" text-anchor="middle" style="fill:var(--text);font-size:19px;font-weight:700">${esc(center)}</text>
      <text x="50%" y="60%" text-anchor="middle" style="fill:var(--muted);font-size:11.5px">${esc(centerSub)}</text></svg>
    <div class="legend grow" style="min-width:210px"></div></div>`);
  const lg = el.querySelector('.legend');
  data.forEach((d, i) => {
    const li = h(`<div class="li"><span class="sw" style="background:${d.color || PALETTE[i % PALETTE.length]}"></span>
      <span class="grow ellipsis">${esc(d.label)}</span><span class="muted num" style="white-space:nowrap">${esc(fmt(d.value))}</span>
      <span class="faint num" style="width:42px;text-align:right">${((100 * d.value) / total).toFixed(1)}%</span></div>`);
    if (d.onClick) li.onclick = d.onClick;
    lg.append(li);
  });
  el.querySelectorAll('circle').forEach((c) => {
    const d = data[+c.dataset.i];
    c.onmousemove = (e) => { c.setAttribute('stroke-width', thickness + 6); tip(e, `<b>${esc(d.label)}</b><br>${esc(fmt(d.value))}${d.sub ? ' · ' + esc(d.sub) : ''}`); };
    c.onmouseleave = () => { c.setAttribute('stroke-width', thickness); tip(null); };
    if (d.onClick) c.onclick = d.onClick;
  });
  return el;
}

/** Horizontal bar list. data: [{label, value, sub?, color?, onClick?}] */
export function hbars(data, { fmt = String, max } = {}) {
  const m = max || Math.max(1, ...data.map((d) => d.value));
  const el = h('<div class="col" style="gap:9px"></div>');
  data.forEach((d, i) => {
    const r = h(`<div style="cursor:${d.onClick ? 'pointer' : 'default'}">
      <div class="row" style="font-size:13px;margin-bottom:4px"><span class="grow ellipsis">${d.labelHtml || esc(d.label)}</span>
      ${d.sub ? `<span class="faint num">${esc(d.sub)}</span>` : ''}<span class="num" style="font-weight:600">${esc(fmt(d.value))}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${(100 * d.value) / m}%;${d.color ? `background:${d.color}` : ''}"></div></div></div>`);
    if (d.onClick) r.onclick = d.onClick;
    el.append(r);
    void i;
  });
  return el;
}

/** Vertical columns, drawn at the container's real width. data: [{label, value, tipHtml?, onClick?}] */
export function columns(data, { height = 190, fmt = String } = {}) {
  const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#007aff';
  const el = h(`<div style="width:100%;height:${height}px"></div>`);
  const draw = () => {
    const W = el.clientWidth || 360;
    const m = Math.max(1, ...data.map((d) => d.value));
    const slot = W / data.length;
    const bw = Math.min(slot * 0.62, 48);
    const ch = height - 24;
    const bars = data.map((d, i) => {
      const bh = Math.max((d.value / m) * (ch - 8), d.value ? 2 : 0);
      const x = (i + 0.5) * slot - bw / 2;
      return `<g data-i="${i}" style="cursor:${d.onClick ? 'pointer' : 'default'}"><rect x="${i * slot}" y="0" width="${slot}" height="${ch}" fill="transparent"/>
        <rect x="${x}" y="${ch - bh}" width="${bw}" height="${bh}" rx="4" fill="${d.color || accent}"/>
        <text x="${(i + 0.5) * slot}" y="${height - 6}" text-anchor="middle">${esc(d.label)}</text></g>`;
    }).join('');
    el.innerHTML = `<svg class="chart" width="${W}" height="${height}">
      <defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8f6bff"/><stop offset="1" stop-color="#6b8cff"/></linearGradient></defs>
      <line x1="0" x2="${W}" y1="${ch}" y2="${ch}" stroke="var(--line)"/>${bars}</svg>`;
    el.querySelectorAll('g[data-i]').forEach((g) => {
      const d = data[+g.dataset.i];
      g.onmousemove = (e) => tip(e, d.tipHtml || `<b>${esc(d.label)}</b><br>${esc(fmt(d.value))}`);
      g.onmouseleave = () => tip(null);
      if (d.onClick) g.onclick = d.onClick;
    });
  };
  new ResizeObserver(draw).observe(el);
  return el;
}

/** Squarified treemap. data: [{label, value, color, sub, onClick}] */
export function treemap(data, { height = 320, fmt = String } = {}) {
  const el = h(`<div style="position:relative;height:${height}px;width:100%"></div>`);
  const draw = () => {
    el.innerHTML = '';
    const W = el.clientWidth || 600;
    const items = data.filter((d) => d.value > 0).sort((a, b) => b.value - a.value);
    const total = items.reduce((a, d) => a + d.value, 0);
    if (!total) return;
    const scale = (W * height) / total;
    const nodes = items.map((d) => ({ ...d, area: d.value * scale }));
    const rects = [];
    let x = 0, y = 0, w = W, hh = height, row = [];
    const worst = (r, side) => {
      const s = r.reduce((a, n) => a + n.area, 0);
      const mx = Math.max(...r.map((n) => n.area)), mn = Math.min(...r.map((n) => n.area));
      return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
    };
    const layout = (r) => {
      const s = r.reduce((a, n) => a + n.area, 0);
      if (w >= hh) {
        const cw = s / hh; let cy = y;
        for (const n of r) { const nh = n.area / cw; rects.push({ n, x, y: cy, w: cw, h: nh }); cy += nh; }
        x += cw; w -= cw;
      } else {
        const rh = s / w; let cx = x;
        for (const n of r) { const nw = n.area / rh; rects.push({ n, x: cx, y, w: nw, h: rh }); cx += nw; }
        y += rh; hh -= rh;
      }
    };
    for (const n of nodes) {
      const side = Math.min(w, hh);
      if (!row.length || worst([...row, n], side) <= worst(row, side)) row.push(n);
      else { layout(row); row = [n]; }
    }
    if (row.length) layout(row);
    rects.forEach((r, i) => {
      const c = h(`<div class="tm-cell" style="left:${r.x}px;top:${r.y}px;width:${r.w}px;height:${r.h}px;background:${r.n.color || PALETTE[i % PALETTE.length]}">
        ${r.w > 60 && r.h > 34 ? `<b>${esc(r.n.label)}</b><span style="opacity:.85">${esc(fmt(r.n.value))}</span>` : ''}</div>`);
      c.onmousemove = (e) => tip(e, `<b>${esc(r.n.label)}</b><br>${esc(fmt(r.n.value))}${r.n.sub ? ' · ' + esc(r.n.sub) : ''}`);
      c.onmouseleave = () => tip(null);
      if (r.n.onClick) c.onclick = r.n.onClick;
      el.append(c);
    });
  };
  new ResizeObserver(draw).observe(el);
  return el;
}
