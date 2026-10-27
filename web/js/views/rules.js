// Auto-cleanup rules: scheduled jobs that move matching files to the recycle bin.
import { $, $$, ago, api, bytes, esc, fail, h, icon, modal, num, runTask, state, toast, userLabel } from '../core.js';

const TARGETS = [
  ['kind:cache', 'Phone thumbnail cache'], ['kind:phonetrash', 'Phone recycle-bin leftovers'], ['smart:junk', 'System junk'],
  ['smart:temp', 'Unfinished downloads & temp'], ['smart:empty', 'Empty files'], ['kind:screenshot', 'Screenshots'],
  ['kind:chat', 'WhatsApp & chat images'], ['kind:web', 'Downloaded & saved images'], ['kind:blurry', 'Blurry photos'],
  ['kind:dark', 'Too dark photos'], ['kind:shortclip', 'Short video clips (<5 s)'], ['kind:screenrec', 'Screen recordings'],
  ['smart:logs', 'Log files'], ['smart:installers', 'Installers & disk images'],
];
const targetKey = (t) => (t.kind ? 'kind:' + t.kind : t.smart ? 'smart:' + t.smart : 'ext:' + t.ext);
const targetLabel = (t) => (TARGETS.find(([k]) => k === targetKey(t)) || [0, t.ext ? `.${t.ext} files` : 'files'])[1];
const parseTarget = (k) => { const [a, b] = k.split(':'); return { [a]: b }; };

export function rulesView(root) {
  const el = h(`<div class="view"><div class="page-head"><div class="grow"><h1>Auto-cleanup rules</h1>
    <p>Let the NAS tidy itself. Rules run on a schedule and only ever move files to the recycle bin.</p></div>
    <button class="btn primary add">${icon('folderPlus')}New rule</button></div>
    <div class="list col" style="gap:12px"></div>
    <h3 style="margin:26px auto 10px">Suggested rules</h3><div class="grid g3 tpl"></div></div>`);
  root.append(el);
  let rules = [];
  const save = async () => { try { rules = (await api('/rules', { rules }, 'PUT')).rules; await load(); } catch (e) { fail(e); } };
  const load = async () => {
    let d;
    try { d = await api('/rules'); } catch (e) { return fail(e); }
    rules = d.rules;
    const list = $('.list', el);
    list.innerHTML = rules.length ? '' : `<div class="card empty" style="padding:30px">${icon('wand')}<div>No rules yet — add one of the suggestions below.</div></div>`;
    for (const r of rules) {
      const row = h(`<div class="card" style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:16px 18px">
        <label class="switch"><input type="checkbox" ${r.enabled ? 'checked' : ''}><span></span></label>
        <div class="grow" style="min-width:220px"><div style="font-weight:700">${esc(r.name)}</div>
          <div class="muted" style="font-size:12.5px">${esc(targetLabel(r.target))}${r.older_days ? ` older than ${r.older_days} days` : ''} · ${r.every} · ${r.users ? r.users.map(userLabel).map(esc).join(', ') : 'all users'}</div>
          <div class="faint" style="font-size:12px">Last run ${r.last_result ? `${ago(r.last_run)} — removed ${num(r.last_result.deleted)} (${bytes(r.last_result.freed)})` : 'never'}</div></div>
        <div style="text-align:right"><div class="muted" style="font-size:12px">matches now</div><b>${num(r.preview.count)} · ${bytes(r.preview.size)}</b></div>
        <button class="btn sm run">${icon('zap')}Run now</button><button class="btn sm ghost icon edit">${icon('edit')}</button><button class="btn sm ghost icon del">${icon('trash')}</button></div>`);
      $('input', row).onchange = (e) => { r.enabled = e.target.checked; save(); };
      $('.run', row).onclick = async () => { if (await runTask(api(`/rules/${r.id}/run`, {}))) load(); };
      $('.edit', row).onclick = () => editRule(r).then((nr) => { if (nr) { Object.assign(r, nr); save(); } });
      $('.del', row).onclick = () => { rules = rules.filter((x) => x !== r); save(); toast('Rule removed', 'info'); };
      list.append(row);
    }
    const tpl = $('.tpl', el);
    tpl.innerHTML = '';
    for (const t of d.templates) {
      const exists = rules.some((r) => targetKey(r.target) === targetKey(t.target) && r.older_days === t.older_days);
      const c = h(`<div class="card hover" style="display:flex;flex-direction:column;gap:8px"><b>${esc(t.name)}</b>
        <div class="muted" style="font-size:12.5px">Runs ${t.every}${t.older_days ? ` · files older than ${t.older_days} days` : ''}</div>
        <button class="btn sm ${exists ? '' : 'primary'}" style="align-self:flex-start" ${exists ? 'disabled' : ''}>${exists ? 'Added' : 'Add rule'}</button></div>`);
      $('button', c).onclick = () => { rules.push({ ...t, enabled: true, users: state.scope }); save(); toast('Rule added — it runs on its schedule, or tap Run now', 'ok'); };
      tpl.append(c);
    }
  };
  $('.add', el).onclick = () => editRule({ name: '', target: { kind: 'cache' }, older_days: 0, every: 'weekly', users: state.scope, enabled: true })
    .then((nr) => { if (nr) { rules.push(nr); save(); } });
  load();
}

async function editRule(r) {
  const users = state.users || [];
  const body = h(`<div class="col" style="gap:12px">
    <input class="input nm" placeholder="Rule name" value="${esc(r.name)}">
    <label class="muted">Files to clean</label><select class="input tg">${TARGETS.map(([k, l]) => `<option value="${k}" ${k === targetKey(r.target) ? 'selected' : ''}>${l}</option>`).join('')}</select>
    <div class="row"><span class="muted">Only files older than</span><input class="input od" type="number" min="0" value="${r.older_days || 0}" style="width:90px"><span class="muted">days</span></div>
    <div class="row"><span class="muted">Run</span><div class="seg ev">${['daily', 'weekly', 'monthly'].map((e) => `<button data-e="${e}" class="${r.every === e ? 'on' : ''}">${e}</button>`).join('')}</div></div>
    <label class="muted">For users</label><div class="row wrap us">${users.map((u) => `<label class="chip ${!r.users || r.users.includes(u.name) ? 'on' : ''}" data-u="${esc(u.name)}">${esc(userLabel(u.name))}</label>`).join('')}</div>
    <div class="notice info pv">${icon('info')}<div>…</div></div></div>`);
  let every = r.every;
  $$('.ev button', body).forEach((b) => (b.onclick = () => { every = b.dataset.e; $$('.ev button', body).forEach((x) => x.classList.toggle('on', x === b)); }));
  $$('.us .chip', body).forEach((c) => (c.onclick = () => { c.classList.toggle('on'); preview(); }));
  const pick = () => {
    const on = $$('.us .chip.on', body).map((c) => c.dataset.u);
    return { target: parseTarget($('.tg', body).value), older_days: +$('.od', body).value || 0, users: on.length === users.length ? null : on };
  };
  const preview = async () => {
    try {
      const p = await api('/rules/preview', pick());
      $('.pv div', body).innerHTML = `Right now this rule matches <b>${num(p.count)}</b> files (<b>${bytes(p.size)}</b>).`;
    } catch (e) { $('.pv div', body).textContent = e.message; }
  };
  $('.tg', body).onchange = preview;
  $('.od', body).oninput = preview;
  preview();
  const ok = await modal({ title: r.id ? 'Edit rule' : 'New rule', body, icon: 'wand', actions: [{ label: 'Cancel', value: false }, { label: 'Save rule', cls: 'primary', value: true }] });
  if (!ok) return null;
  const p = pick();
  return { ...r, ...p, every, name: $('.nm', body).value.trim() || targetLabel(p.target) };
}
