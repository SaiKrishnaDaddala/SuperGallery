// Photo & video categories: memes/forwards, screenshots, documents, low quality, blurry, dark, recordings…
import { $, api, bytes, esc, fail, h, icon, num, on, state } from '../core.js';
import { resultList } from '../resultlist.js';

const TINT = {
  camera: ['#5ac8fa', '#007aff'], chat: ['#30d158', '#248a3d'], web: ['#ff9f0a', '#ff2d55'], cache: ['#8e8e93', '#48484a'], phonetrash: ['#ff6961', '#ff3b30'], screenshot: ['#64d2ff', '#5e5ce6'],
  document: ['#d1d1d6', '#8e8e93'], lowq: ['#ffd60a', '#ff9500'], blurry: ['#bf5af2', '#5e5ce6'],
  dark: ['#48484a', '#1c1c1e'], tiny: ['#63e6be', '#30b0c7'], other: ['#a2845e', '#7c6a4f'],
  screenrec: ['#ff375f', '#bf5af2'], msgvideo: ['#30d158', '#248a3d'], camvideo: ['#0a84ff', '#5e5ce6'],
  shortclip: ['#ff9f0a', '#ff375f'], uhd: ['#5e5ce6', '#bf5af2'], longvideo: ['#64d2ff', '#0a84ff'],
};
const CLEANABLE = new Set(['cache', 'phonetrash', 'chat', 'web', 'screenshot', 'lowq', 'blurry', 'dark', 'tiny', 'screenrec', 'msgvideo', 'document', 'shortclip']);
const SAFE = new Set(['cache', 'phonetrash']);

export function scopeBanner() {
  if (!state.scope) return '';
  return `<div class="scope-banner">${icon('users')}<span>Showing only <b>${state.scope.map((u) => esc(u === 'shared' ? 'Shared folders' : u)).join(', ')}</b>. Actions stay inside ${state.scope.length > 1 ? 'these users' : 'this user'}.</span></div>`;
}

export function categoriesView(root, params, sub) {
  if (sub[0]) return detail(root, sub[0]);
  const el = h(`<div class="view"><div class="page-head"><div class="grow"><h1>Photo & video categories</h1>
    <p>Every photo and video is sorted automatically on your NAS — no cloud. Review a category and clean it in one tap.</p></div></div>
    ${scopeBanner()}<div class="pend"></div><div class="grid g3 cards"></div></div>`);
  root.append(el);
  const load = async () => {
    let r;
    try { r = await api('/categories'); } catch (e) { return fail(e); }
    $('.pend', el).innerHTML = r.pending ? `<div class="notice info" style="margin-bottom:16px">${icon('sparkles')}<div>Analyzing <b>${num(r.pending)}</b> photos in the background — categories fill in as it goes.</div></div>` : '';
    const box = $('.cards', el);
    box.innerHTML = '';
    for (const c of r.categories) {
      const [a, b] = TINT[c.key] || TINT.other;
      const tiles = c.sample.slice(0, 6).map((id) => `<img loading="lazy" src="/api/thumb?id=${id}&s=256" onerror="this.style.visibility='hidden'">`);
      while (tiles.length < 6) tiles.push(`<div class="ph" style="background:linear-gradient(145deg,${a}22,${b}33)"></div>`);
      const card = h(`<a class="card cat-card" href="#/categories/${c.key}" style="color:inherit">
        <div class="mosaic">${tiles.join('')}</div>
        <div class="body"><div class="t"><span class="avatar" style="background-color:${b};border-radius:6px">${icon(c.icon).replace('class="i ', 'style="width:13px;height:13px" class="i ')}</span>${esc(c.title)}
          ${SAFE.has(c.key) && c.count ? '<span class="badge ok" style="margin-left:auto">safe to delete</span>' : CLEANABLE.has(c.key) && c.count ? '<span class="badge warn" style="margin-left:auto">review</span>' : ''}</div>
        <div class="d">${esc(c.desc)}</div>
        <div class="row" style="margin-top:8px"><b style="font-size:20px;letter-spacing:-.02em">${num(c.count)}</b><span class="muted">${c.video ? 'videos' : 'items'}</span><span class="grow"></span><b class="muted">${bytes(c.size)}</b></div></div></a>`);
      if (!c.count) card.style.opacity = '.55';
      box.append(card);
    }
  };
  load();
  return on('changed', load);
}

function detail(root, key) {
  const el = h(`<div class="view" style="display:flex;flex-direction:column">
    <div class="page-head"><a class="btn icon" href="#/categories">${icon('left')}</a><div class="grow"><h1 class="t">…</h1><p class="d"></p></div>
      <button class="btn danger all">${icon('trash')}Delete all</button></div>${scopeBanner()}</div>`);
  root.append(el);
  const list = resultList({ filter: { kind: key }, sort: 'size', order: 'desc', mode: 'grid', empty: 'Nothing in this category' });
  el.append(list.el);
  api('/categories').then((r) => {
    const c = r.categories.find((x) => x.key === key);
    if (!c) return;
    $('.t', el).textContent = c.title;
    $('.d', el).textContent = `${c.desc} · ${num(c.count)} files · ${bytes(c.size)}`;
    if (!c.count) $('.all', el).disabled = true;
  }).catch(fail);
  $('.all', el).onclick = () => { list.selectAll(); list.deleteSelected(); };
}
