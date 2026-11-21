// Explore: the library by who and what is in it — people, things recognised in photos, and collections.
import { $, api, bytes, esc, h, icon, num, on } from '../core.js';
import { hasFeature } from '../features.js';
import { resultList } from '../resultlist.js';
import { scopeBanner } from './categories.js';

const faceImage = (id) => `/api/faces/${id}/image`;

export function exploreView(root, params, sub = []) {
  if (sub[0] === 'things') return sub[1] ? thingView(root, decodeURIComponent(sub[1])) : thingsView(root);
  const el = h(`<div class="view explore-view">
    <div class="page-head"><div class="grow"><h1>Explore</h1><p>Find photos by the people, things and kinds of pictures in them.</p></div></div>
    ${scopeBanner()}
    <section class="ex-section ex-people" hidden><div class="section-title"><h2>People</h2><a href="#/people">View all${icon('right')}</a></div><div class="ex-faces"></div></section>
    <section class="ex-section ex-things" hidden><div class="section-title"><h2>Things</h2><a href="#/explore/things">View all${icon('right')}</a></div><div class="ex-chips"></div></section>
    <section class="ex-section ex-cats"><div class="section-title"><h2>Collections</h2><a href="#/categories">View all${icon('right')}</a></div>
      <div class="ex-grid"><div class="list-skel grid">${'<div></div>'.repeat(8)}</div></div></section>
  </div>`);
  root.append(el);
  let alive = true;

  async function people() {
    if (!hasFeature('people')) return;
    let r;
    try { r = await api('/people?limit=16'); } catch { return; }
    if (!alive || !r.items?.length) return;
    $('.ex-faces', el).innerHTML = r.items.map((p) => `<a class="ex-face" href="#/people?id=${p.id}" title="${esc(p.name || 'Unnamed person')} · ${num(p.photos)} photos">
      <img loading="lazy" alt="" src="${faceImage(p.cover)}" data-fallback="hide"><span>${esc(p.name || 'Add a name')}</span></a>`).join('');
    $('.ex-people', el).hidden = false;
  }

  async function things() {
    let r;
    try { r = await api('/tags?limit=24'); } catch { return; }
    if (!alive || !r.tags?.length) return;
    $('.ex-chips', el).innerHTML = thingTiles(r.tags);
    $('.ex-things', el).hidden = false;
  }

  async function collections() {
    let r;
    try { r = await api('/categories'); } catch (e) {
      $('.ex-grid', el).innerHTML = `<div class="empty">${icon('alert')}<div>Couldn’t load collections.</div><button class="btn sm retry">${icon('refresh')}Try again</button></div>`;
      $('.retry', el).onclick = collections;
      return;
    }
    if (!alive) return;
    const cats = r.categories.filter((c) => c.count);
    $('.ex-grid', el).innerHTML = cats.length ? cats.map((c) => `<a class="ex-card" href="#/categories/${c.key}">
      <div class="ex-cover">${c.sample[0] ? `<img loading="lazy" alt="" src="/api/thumb?id=${c.sample[0]}&s=512" data-fallback="hide">` : icon(c.icon)}</div>
      <b>${esc(c.title)}</b><span>${num(c.count)} ${c.video ? 'videos' : 'items'} · ${bytes(c.size)}</span></a>`).join('')
      : `<div class="empty">${icon('images')}<div>${r.pending ? 'Photos are still being sorted into collections.' : 'Nothing to show yet.'}</div></div>`;
  }

  people(); things(); collections();
  const off = on('changed', () => { people(); things(); collections(); });
  return () => { alive = false; off(); };
}

const thingTiles = (tags) => tags.map((t) => `<a class="ex-thing" href="#/explore/things/${encodeURIComponent(t.label)}">
  <img loading="lazy" alt="" src="/api/thumb?id=${t.cover}&s=256" data-fallback="hide"><span>${esc(t.label)}</span><small>${num(t.count)}</small></a>`).join('');

// Every thing recognised in the photos.
function thingsView(root) {
  const el = h(`<div class="view explore-view">
    <div class="page-head"><a class="btn icon ghost" href="#/explore" aria-label="Back to Explore">${icon('left')}</a><div class="grow"><h1>Things</h1>
      <p>Recognised on your NAS from what is in each photo. Matches can be imperfect.</p></div></div>
    ${scopeBanner()}<div class="ex-chips"><div class="list-skel grid">${'<div></div>'.repeat(12)}</div></div></div>`);
  root.append(el);
  let alive = true;
  const load = async () => {
    let r;
    try { r = await api('/tags?limit=200'); } catch (e) {
      $('.ex-chips', el).innerHTML = `<div class="empty">${icon('alert')}<div>Couldn’t load things.</div><div class="muted small">${esc(e.message)}</div></div>`;
      return;
    }
    if (!alive) return;
    $('.ex-chips', el).innerHTML = r.tags.length ? thingTiles(r.tags)
      : `<div class="empty">${icon('images')}<div>Nothing recognised yet. Photos are tagged after “Photo meaning” has looked at them.</div><a class="btn sm" href="#/search?mode=photos">Open photo search</a></div>`;
  };
  load();
  const off = on('changed', load);
  return () => { alive = false; off(); };
}

// The photos of one thing, as a list or thumbnails.
function thingView(root, label) {
  const el = h(`<div class="view fill">
    <div class="page-head"><a class="btn icon ghost" href="#/explore/things" aria-label="Back to things">${icon('left')}</a>
      <div class="grow"><h1 class="thing-title"></h1><p>Photos where SuperGallery recognised this. Matches can be imperfect.</p></div></div>${scopeBanner()}</div>`);
  $('.thing-title', el).textContent = label.charAt(0).toUpperCase() + label.slice(1);
  root.append(el);
  const list = resultList({ filter: { tag: label }, sort: 'ts', order: 'desc', mode: 'grid', id: 'things', empty: `No photos of ${label} yet` });
  el.append(list.el);
  return () => list.destroy();
}
