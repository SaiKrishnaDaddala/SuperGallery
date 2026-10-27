import { $, $$, containDialogFocus, esc, h, icon } from './core.js';

// Navigation and the existing natural-language search engine, in one keyboard entry point.
export function openCommandPalette(groups) {
  if ($('.command-dialog')) return;
  const previous = document.activeElement;
  const dialog = h(`<dialog class="command-dialog" aria-label="Search and commands"><form method="dialog" class="command-search">${icon('search')}<input aria-label="Find a page or search files" placeholder="Search your library" autocomplete="off"><button class="kbd" aria-label="Close commands">${icon('x')}</button></form><div class="command-results" role="listbox" aria-label="Results"></div><footer>↑ ↓ to navigate <span>↵ to open</span><span>esc to close</span></footer></dialog>`);
  document.body.append(dialog);
  const input = $('input', dialog), results = $('.command-results', dialog);
  const links = groups.flatMap(([, items]) => items).concat([['trash', 'Recently deleted', 'trash'], ['settings', 'Settings', 'settings']]);
  let index = 0, matches = [];
  const select = () => {
    $$('[role="option"]', results).forEach((el, i) => { el.classList.toggle('selected', i === index); el.setAttribute('aria-selected', String(i === index)); });
    input.setAttribute('aria-activedescendant', `command-${index}`);
    results.children[index]?.scrollIntoView({block:'nearest'});
  };
  const open = (i) => { const item = matches[i]; if (!item) return; dialog.close(); location.hash = item.href; };
  const render = () => {
    const q = input.value.trim();
    matches = links.filter(([, label]) => label.toLowerCase().includes(q.toLowerCase())).map(([key, label, ic]) => ({label, ic, href:`#/${key}`, sub:'Go to page'}));
    if (q) matches.unshift({label:`Search for “${q}”`, sub:'Search your files · understands size, type and date', ic:'search', href:'#/search?nl='+encodeURIComponent(q)});
    else matches = matches.slice(0, 9);
    results.innerHTML = matches.map((m,i) => `<button type="button" role="option" id="command-${i}" aria-selected="false">${icon(m.ic)}<span><b>${esc(m.label)}</b><small>${m.sub}</small></span>${icon('right')}</button>`).join('');
    $$('button', results).forEach((button,i) => button.onclick = () => open(i));
    index = 0; select();
  };
  input.setAttribute('role','combobox'); input.setAttribute('aria-expanded','true'); input.setAttribute('aria-controls','command-options'); results.id = 'command-options';
  input.oninput = render;
  input.onkeydown = e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); index = (index + (e.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length; select(); }
    if (e.key === 'Enter') { e.preventDefault(); open(index); }
  };
  dialog.onclick = e => { if (e.target === dialog) dialog.close(); };
  dialog.onclose = () => { dialog.remove(); previous?.focus(); };
  containDialogFocus(dialog);
  render(); dialog.showModal(); input.focus();
}
