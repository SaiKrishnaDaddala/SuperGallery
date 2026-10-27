import { $, $$, ago, api, bytes, CAT_COLORS, esc, h, icon, num, on, poll, thumbUrl, toast } from '../core.js';
import { scopeBanner } from './categories.js';
import { hasFeature } from '../features.js';
import { lightbox } from '../lightbox.js';

const TYPES = [['image','Photos','images'],['video','Videos','film'],['document','Documents','fileText'],['audio','Audio','music']];
const LABELS = {image:'Photos',video:'Videos',document:'Documents',audio:'Audio',archive:'Archives',code:'Code',other:'Other'};
const TIP_ICONS = {dupes:'copy',similar:'layers',phonetrash:'trash',chat:'images',screenshot:'monitor',old_large:'archive',installers:'package',empty:'file'};

export function dashboardView(root) {
  let disposed = false, revision = 0;
  const el = h(`<div class="view home-view"><div class="page-head"><div class="grow"><h1>Library</h1><p class="library-caption">Your photos, files, and storage.</p></div><button class="btn rescan" aria-label="Refresh library">${icon('refresh')}<span>Refresh</span></button></div>${scopeBanner()}<div class="home-body"><div class="home-skeleton" role="status" aria-label="Loading your library"><div></div><div></div><div></div></div></div></div>`);
  root.append(el);
  const scan = $('.rescan',el);
  scan.onclick = async () => {
    scan.disabled = true;
    try { await api('/scan',{}); await poll(true); toast('Library scan started. View progress in Activity.'); }
    catch(e) { toast(esc(e.message),'err'); }
    finally { scan.disabled = false; }
  };
  async function load() {
    const current = ++revision;
    let s, tips;
    try { [s,tips] = await Promise.all([api('/stats'), api('/insights')]); }
    catch(e) {
      if (disposed || current !== revision) return;
      $('.home-body',el).innerHTML = `<div class="card home-error">${icon('hdd')}<h2>Unable to load your library</h2><p>${esc(e.message)}</p><button class="btn primary retry">Try again</button></div>`;
      $('.retry',el).onclick = load; return;
    }
    if (disposed || current !== revision) return;
    $('.library-caption',el).textContent = `${num(s.total_files)} items · ${s.roots.length} library locations`;
    const cats = Object.fromEntries(s.by_cat.map(c => [c.cat,c]));
    const total = s.total_size || 0;
    const sorted = s.by_cat.filter(c => c.size).sort((a,b) => b.size-a.size);
    let angle = 0;
    const stops = sorted.map(c => { const start = angle; angle += total ? c.size/total*360 : 0; return `${CAT_COLORS[c.cat] || '#8e8e93'} ${start}deg ${angle}deg`; });
    // Suggestions overlap; show individual estimates without adding them together.
    const suggestions = tips.filter(t => t.kind !== 'info').sort((a,b) => b.size-a.size).slice(0,4);
    $('.home-body',el).innerHTML = `
      <div class="home-lead">
        <section class="recent-module" aria-labelledby="recent-title"><div class="section-title"><h2 id="recent-title">Recent photos</h2><a href="#/gallery">Show all ${icon('right')}</a></div><div class="recent-grid" aria-busy="true"><div class="recent-loading" role="status">Loading photos…</div></div></section>
        <section class="storage-module card" aria-labelledby="storage-title"><div class="section-title"><h2 id="storage-title">Storage</h2><a href="#/analytics" aria-label="View storage details">Details ${icon('right')}</a></div><div class="storage-ring" style="--storage-colors:${stops.length ? stops.join(',') : 'var(--fill) 0deg 360deg'}"><div><strong>${bytes(total)}</strong><span>in your library</span></div></div><div class="storage-legend">${sorted.slice(0,3).map(c => `<a href="#/search?cat=${encodeURIComponent(c.cat)}&sort=size"><span class="legend-dot" style="background:${CAT_COLORS[c.cat] || '#8e8e93'}"></span><span>${LABELS[c.cat] || esc(c.cat)}</span><b>${bytes(c.size)}</b></a>`).join('') || '<span class="muted">No files indexed yet</span>'}</div><p class="storage-note">Indexed files across your library locations.</p></section>
      </div>
      <section class="library-types" aria-label="Browse by file type">${TYPES.map(([cat,label,ic]) => {
        const c = cats[cat] || {};
        return `<a class="type-tile type-${cat}" href="${cat === 'image' || cat === 'video' ? '#/gallery?kind='+cat : '#/search?cat='+cat}"><span class="type-icon">${icon(ic)}</span><div class="grow"><h3>${label}</h3><p>${num(c.count)} items</p></div>${icon('right')}</a>`;
      }).join('')}</section>
      <div class="home-lower"><section class="card review-list" ${hasFeature('cleanup')?'':'hidden'}><div class="section-title"><div><h2>Worth a look</h2><p>A few ways to organize your library.</p></div><a href="#/quickclean">Show all ${icon('right')}</a></div>${suggestions.length ? suggestions.map(t => `<a class="suggestion-row" href="${esc(t.view)}"><span class="suggestion-icon">${icon(TIP_ICONS[t.kind] || 'sparkles')}</span><div class="grow"><h3>${esc(t.title)}</h3><p>${esc(t.text)}</p></div><span class="suggestion-size">${bytes(t.size || 0)}<small>to review</small></span>${icon('right')}</a>`).join('') : `<div class="empty">${icon(s.total_files ? 'check' : 'scan')}<h3>${s.total_files ? 'All caught up' : 'Your library starts here'}</h3><p>${s.total_files ? 'New suggestions appear after a library scan.' : 'Refresh your library to find your photos and files.'}</p></div>`}<div class="review-footnote">${icon('info')}You choose what to keep. Nothing is selected automatically.</div></section>
      <section class="card locations-card"><div class="section-title"><h2>Locations</h2>${icon('hdd')}</div><div class="location-list"><p class="muted">Loading storage…</p></div><a class="location-link" href="#/files">Browse files ${icon('right')}</a></section></div>
      <footer class="home-footer"><span><span class="status-dot"></span>${s.last_scan ? `Updated ${ago(s.last_scan)}` : 'Waiting for the first scan'}${s.photos_pending ? ` · ${num(s.photos_pending)} photos awaiting analysis` : ''}</span><a href="#/settings">Library settings ${icon('right')}</a></footer>`;
    // Photo failure must not hide storage or review suggestions.
    api('/query', {filter:{cat:['image']},sort:'ts',order:'desc',limit:5,offset:0}).then(r => {
      if (disposed || current !== revision) return;
      const grid = $('.recent-grid',el), items = r.items || [];
      grid.setAttribute('aria-busy','false');
      grid.innerHTML = items.length ? items.map((it,i) => `<button class="recent-photo" data-index="${i}" aria-label="Open ${esc(it.name)}"><img src="${thumbUrl(it,600)}" alt="" loading="${i === 0 ? 'eager' : 'lazy'}" decoding="async"><span class="recent-date">${new Date(it.ts * 1000).toLocaleDateString(undefined,{month:'short',day:'numeric'})}</span></button>`).join('') : `<a class="recent-empty" href="#/gallery">${icon('images')}<strong>Your photos belong here</strong><span>Photos appear after your library is scanned.</span></a>`;
      $$('.recent-photo',grid).forEach(button => {
        button.onclick = () => lightbox([...items],+button.dataset.index,{onDeleted:load});
        $('img',button).onerror = () => { button.classList.add('preview-missing'); $('img',button).remove(); button.insertAdjacentHTML('afterbegin',icon('images')); };
      });
    }).catch(() => { if (!disposed && current === revision) { $('.recent-grid',el).setAttribute('aria-busy','false'); $('.recent-grid',el).innerHTML = '<a class="recent-empty" href="#/gallery">Photo previews are unavailable. Open Photos to try again.</a>'; } });
    try {
      const data = await api('/browse?path=');
      if (disposed || current !== revision) return;
      $('.location-list',el).innerHTML = data.entries.map(v => {
        const d=v.disk, pct=d?.total ? Math.min(100,100*d.used/d.total) : 0;
        return `<a class="location-row" href="#/files?path=${encodeURIComponent(v.path)}"><div class="row">${icon(v.name === 'Personal' ? 'users' : 'hdd')}<b class="grow">${esc(v.name)}</b>${icon('right')}</div><div class="location-meta">${num(v.count)} files <span>${bytes(v.size)}</span></div>${d ? `<div class="progress"><div style="width:${pct}%;${pct>90?'background:var(--warn)':''}"></div></div><p>${bytes(d.free)} available on this disk</p>` : ''}</a>`;
      }).join('') || '<p class="muted">No library locations configured.</p>';
    } catch { if (!disposed && current === revision) $('.location-list',el).innerHTML = '<p class="muted">Storage details are temporarily unavailable.</p>'; }
  }
  load(); const off=on('changed',load);
  return () => { disposed=true; off(); };
}
