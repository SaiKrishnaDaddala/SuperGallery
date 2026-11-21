// Public share page: the photos of one share link, with a simple viewer. No sign-in, no other library access.
const token = decodeURIComponent(location.pathname.split('/').pop());
const base = `/api/public/${encodeURIComponent(token)}`;
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const PLAYABLE = new Set(['mp4', 'webm', 'm4v', 'mov', 'ogv']);
let items = [], at = 0;

async function load() {
  let r;
  try {
    const response = await fetch(base, { headers: { 'X-SG-Request': '1' } });
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'This link is not available.');
    r = await response.json();
  } catch (e) {
    $('h1').textContent = 'Link not available';
    $('.meta').textContent = e.message;
    return;
  }
  items = r.items;
  document.title = r.title;
  $('h1').textContent = r.title;
  const until = new Date(r.expires * 1000).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  $('.meta').textContent = `${items.length} ${items.length === 1 ? 'item' : 'items'} · available until ${until}`;
  $('.grid').innerHTML = items.map((it, i) => `<button class="tile" data-i="${i}" style="--ar:${it.width && it.height ? Math.min(3, Math.max(.33, it.width / it.height)).toFixed(3) : 1}" aria-label="Open ${esc(it.name)}">
    <img loading="lazy" alt="" src="${base}/thumb/${i}?s=512">${it.cat === 'video' ? '<span class="play">&#x25B6;</span>' : ''}</button>`).join('');
  document.querySelectorAll('.tile').forEach((b) => (b.onclick = () => open(+b.dataset.i)));
}

function show() {
  const it = items[at];
  $('.name').textContent = it.name;
  $('.pos').textContent = `${at + 1} / ${items.length}`;
  $('.dl').href = `${base}/file/${at}?download=1`;
  $('.stage').innerHTML = it.cat === 'video' && PLAYABLE.has(it.ext)
    ? `<video src="${base}/file/${at}" controls autoplay playsinline poster="${base}/thumb/${at}?s=1600"></video>`
    : `<img alt="" src="${base}/thumb/${at}?s=1600">`;
}

function open(i) { at = i; show(); $('.viewer').showModal(); }
function go(d) { at = (at + d + items.length) % items.length; show(); }
$('.prev').onclick = () => go(-1);
$('.next').onclick = () => go(1);
$('.close').onclick = () => $('.viewer').close();
$('.viewer').addEventListener('close', () => { $('.stage').innerHTML = ''; });
document.addEventListener('keydown', (e) => {
  if (!$('.viewer').open) return;
  if (e.key === 'ArrowRight') go(1);
  if (e.key === 'ArrowLeft') go(-1);
});
load();
let startX = null;
$('.stage').addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
$('.stage').addEventListener('touchend', (e) => {
  if (startX === null) return;
  const dx = e.changedTouches[0].clientX - startX;
  startX = null;
  if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
});
