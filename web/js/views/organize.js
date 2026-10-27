// Auto-organize: move files into a folder structure by date / type, with a dry-run preview.
import { $, $$, api, CAT_LABEL, confirmBox, esc, fail, h, icon, num, pickFolder, runTask, shortPath } from '../core.js';

const PATTERNS = [
  ['{yyyy}/{mm}', '2024 / 03'], ['{yyyy}/{yyyy}-{mm}-{dd}', '2024 / 2024-03-17'], ['{yyyy}', '2024'],
  ['{cat}/{yyyy}', 'image / 2024'], ['{ext}', 'jpg'], ['{cat}', 'video'],
];

export function organizeView(root) {
  const st = { src: '', dest: '', cats: new Set(['image', 'video']), pattern: '{yyyy}/{mm}' };
  const el = h(`<div class="view"><div class="page-head"><div class="grow"><h1>Auto-organize</h1>
    <p>Sort a messy folder (camera uploads, Downloads, phone backups) into a clean structure by date or type. Preview first, nothing moves until you confirm.</p></div></div>
    <div class="grid g2"><div class="card col" style="gap:14px">
      <div><div class="muted" style="margin-bottom:6px">1 · Take files from</div><button class="btn src">${icon('folder')}<span>Choose folder…</span></button></div>
      <div><div class="muted" style="margin-bottom:6px">2 · Only these kinds</div><div class="row wrap cats">${Object.entries(CAT_LABEL).map(([k, v]) => `<button class="chip" data-c="${k}">${v}</button>`).join('')}</div></div>
      <div><div class="muted" style="margin-bottom:6px">3 · Move them into</div><button class="btn dst">${icon('folder')}<span>Choose destination…</span></button></div>
      <div><div class="muted" style="margin-bottom:6px">4 · Using this structure</div><div class="col pats" style="gap:6px">${PATTERNS.map(([p, ex]) => `<label class="chk"><input type="radio" name="pat" value="${p}" ${p === st.pattern ? 'checked' : ''}><span class="mono">${esc(p)}</span><span class="faint">e.g. ${esc(ex)}/</span></label>`).join('')}
        <label class="chk"><input type="radio" name="pat" value="custom"><input class="input sm custom" placeholder="custom: {yyyy}/{mm}-{dd}" style="width:220px"></label></div></div>
      <div class="row"><button class="btn prev">${icon('eye')}Preview</button><button class="btn primary run" disabled>${icon('wand')}Organize now</button></div>
      <div class="notice info">${icon('info')}<div>Dates come from the photo's EXIF "taken" time when available, otherwise the file's modified date. Name clashes get a (1) suffix — nothing is overwritten.</div></div>
    </div><div class="card"><h3>${icon('list')}Preview<span class="right muted cnt"></span></h3><div class="pv muted">Choose a source and destination, then press Preview.</div></div></div></div>`);
  root.append(el);
  const pat = () => { const v = $('input[name=pat]:checked', el).value; return v === 'custom' ? $('.custom', el).value.trim() || '{yyyy}' : v; };
  const filter = () => ({ dir: st.src, cat: [...st.cats] });
  const draw = () => $$('.cats .chip', el).forEach((c) => c.classList.toggle('on', st.cats.has(c.dataset.c)));
  $$('.cats .chip', el).forEach((c) => (c.onclick = () => { st.cats.has(c.dataset.c) ? st.cats.delete(c.dataset.c) : st.cats.add(c.dataset.c); draw(); }));
  draw();
  $('.src', el).onclick = async () => { const d = await pickFolder('Take files from', st.src); if (d) { st.src = d; $('.src span', el).textContent = shortPath(d); } };
  $('.dst', el).onclick = async () => { const d = await pickFolder('Move into', st.dest || st.src); if (d) { st.dest = d; $('.dst span', el).textContent = shortPath(d); } };
  $('.prev', el).onclick = async () => {
    if (!st.src || !st.dest) return fail(new Error('Choose a source and a destination folder'));
    try {
      const r = await api('/organize/preview', { filter: filter(), dest: st.dest, pattern: pat() });
      $('.cnt', el).textContent = `${num(r.count)} files will move`;
      $('.pv', el).className = 'pv';
      $('.pv', el).innerHTML = r.count ? `<div style="max-height:520px;overflow:auto">${r.sample.map((m) => `<div class="list-row mono" style="font-size:12px"><span class="ellipsis muted" style="flex:1">${esc(shortPath(m.from))}</span>${icon('right')}<span class="ellipsis" style="flex:1">${esc(shortPath(m.to))}</span></div>`).join('')}${r.count > r.sample.length ? `<div class="faint" style="padding:8px">…and ${num(r.count - r.sample.length)} more</div>` : ''}</div>` : '<div class="muted">Nothing to move — everything is already in place.</div>';
      $('.run', el).disabled = !r.count;
      $('.run', el).onclick = async () => {
        if (!(await confirmBox('Organize files', `Move <b>${num(r.count)}</b> files into <span class="mono">${esc(shortPath(st.dest))}</span>?`, 'Organize'))) return;
        const t = await runTask(api('/organize/run', { filter: filter(), dest: st.dest, pattern: pat() }));
        if (t) $('.prev', el).click();
      };
    } catch (e) { fail(e); }
  };
}
