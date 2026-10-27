// Full-screen media viewer with keyboard navigation, info panel and quick delete.
import { $, api, bytes, confirmDelete, containDialogFocus, date, esc, fail, h, icon, num, rawUrl, shortPath, thumbUrl, toast } from './core.js';

const VIDEO_PLAYABLE = new Set(['mp4', 'webm', 'm4v', 'mov', 'ogv']);
const AUDIO = new Set(['mp3', 'm4a', 'aac', 'ogg', 'opus', 'wav', 'flac']);

/** items: [{id?, path, name, ext, cat, size, ...}]; onDeleted(item) lets the caller update its list. */
export function lightbox(items, index = 0, { onDeleted, onClose } = {}) {
  let i = index;
  const previous = document.activeElement;
  let closed = false;
  let showInfo = localStorage.getItem('lb-info') === '1';
  const el = h(`<dialog class="lightbox" aria-label="Media preview"><div class="lb-stage">
      <div class="lb-top"><div class="grow ellipsis name"></div><span class="pos muted"></span>
        <a class="btn sm dl">${icon('download')}Download</a>
        <button class="btn sm share">${icon('upload')}Share</button>
        <button class="btn sm inf">${icon('info')}Info</button>
        <button class="btn sm del">${icon('trash')}Delete</button>
        <button class="btn sm icon close" aria-label="Close preview">${icon('x')}</button></div>
      <div class="media" style="display:contents"></div>
      <button class="lb-btn prev" aria-label="Previous item" style="left:16px">${icon('left')}</button>
      <button class="lb-btn next" aria-label="Next item" style="right:16px">${icon('right')}</button>
    </div><div class="lb-side hidden"></div></dialog>`);
  const side = $('.lb-side', el);

  const show = async () => {
    const it = items[i];
    if (!it) return close();
    $('.name', el).textContent = it.name;
    $('.pos', el).textContent = `${i + 1} / ${items.length}`;
    $('.dl', el).href = rawUrl(it, true);
    const m = $('.media', el);
    if (it.cat === 'video' && VIDEO_PLAYABLE.has(it.ext)) {
      m.innerHTML = `<video src="${rawUrl(it)}" controls autoplay playsinline poster="${thumbUrl(it, 1600)}"></video>`;
      if(Number.isFinite(it.start_seconds)&&it.start_seconds>0){const player=$('video',m);player.addEventListener('loadedmetadata',()=>{player.currentTime=Math.min(it.start_seconds,Math.max(0,player.duration-.1));},{once:true});}
    } else if (it.cat === 'audio' && AUDIO.has(it.ext)) {
      m.innerHTML = `<audio src="${rawUrl(it)}" controls autoplay></audio>`;
    } else if (it.ext === 'pdf') {
      m.innerHTML = `<iframe src="${rawUrl(it)}" style="width:100%;height:100vh;border:0;background:#fff"></iframe>`;
    } else {
      m.innerHTML = `<img src="${thumbUrl(it, 1600)}" alt="">`;
      const img = $('img', m);
      img.onerror = () => { m.innerHTML = `<div class="empty">${icon('eyeOff')}<div>No preview for this file type</div></div>`; };
    }
    side.classList.toggle('hidden', !showInfo);
    if (showInfo) {
      side.innerHTML = '<div class="muted">Loading…</div>';
      try {
        const d = await api('/info?path=' + encodeURIComponent(it.path));
        if (items[i] !== it) return;
        side.innerHTML = `<h3 style="margin:0 0 12px;word-break:break-all">${esc(d.name)}</h3><div class="kv">
          <div>Size</div><div>${bytes(d.size)} <span class="faint">(${num(d.size)} B)</span></div>
          ${d.width ? `<div>Dimensions</div><div>${d.width} × ${d.height} (${((d.width * d.height) / 1e6).toFixed(1)} MP)</div>` : ''}
          ${d.taken ? `<div>Taken</div><div>${date(d.taken, true)}</div>` : ''}
          <div>Modified</div><div>${date(d.mtime, true)}</div>
          ${d.sharpness != null ? `<div>Sharpness</div><div>${d.sharpness.toFixed(0)} ${d.sharpness < 40 ? '<span class="badge warn">blurry</span>' : ''}</div>` : ''}
          <div>Folder</div><div class="mono">${esc(shortPath(d.path.split('/').slice(0, -1).join('/')))}</div>
          ${d.hash ? `<div>Checksum</div><div class="mono">${esc(d.hash)}</div>` : ''}
          ${d.copies?.length ? `<div>Copies</div><div>${d.copies.map((c) => `<div class="mono">${esc(shortPath(c))}</div>`).join('')}</div>` : ''}
        </div>`;
      } catch (e) { side.textContent = e.message; }
    }
  };
  const go = (d) => { i = (i + d + items.length) % items.length; show(); };
  const close = () => { if (closed) return; closed = true; el.close(); el.remove(); document.removeEventListener('keydown', key, true); previous?.focus(); onClose?.(); };
  const del = async () => {
    const it = items[i];
    const t = await confirmDelete({ ids: it.id ? [it.id] : undefined, paths: it.id ? undefined : [it.path], count: 1, size: it.size });
    if (t?.status === 'done') {
      items.splice(i, 1);
      onDeleted?.(it);
      if (!items.length) return close();
      if (i >= items.length) i = items.length - 1;
      show();
    }
  };
  const key = (e) => {
    if (document.querySelector('.modal-bg')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowRight') go(1);
    else if (e.key === 'ArrowLeft') go(-1);
    else if (e.key === 'Delete') del();
    else if (e.key === 'i') $('.inf', el).click();
    else return;
    e.preventDefault(); e.stopPropagation();
  };
  $('.prev', el).onclick = () => go(-1);
  $('.next', el).onclick = () => go(1);
  $('.close', el).onclick = close;
  $('.del', el).onclick = del;
  $('.share',el).onclick=async()=>{const it=items[i],button=$('.share',el);try{button.disabled=true;if(navigator.share&&it.size<=50*1024*1024){const response=await fetch(rawUrl(it));if(!response.ok)throw new Error('Could not prepare the file for sharing.');const file=new File([await response.blob()],it.name,{type:response.headers.get('content-type')||''});if(navigator.canShare?.({files:[file]})){await navigator.share({files:[file],title:it.name});return;}}await navigator.clipboard.writeText(new URL(rawUrl(it),location.origin).href);toast('Private NAS link copied. The recipient needs NAS access and a SuperGallery login.');}catch(e){if(e.name!=='AbortError')fail(e);}finally{button.disabled=false;}};
  $('.inf', el).onclick = () => { showInfo = !showInfo; localStorage.setItem('lb-info', showInfo ? '1' : '0'); show(); };
  if (items.length < 2) { $('.prev', el).remove(); $('.next', el).remove(); }
  document.addEventListener('keydown', key, true);
  document.body.append(el);
  containDialogFocus(el);
  el.addEventListener('cancel', e => { e.preventDefault(); close(); });
  el.showModal();
  show();
  $('.close',el).focus();
}
