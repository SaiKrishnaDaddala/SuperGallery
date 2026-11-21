// Favourites: the photos and files you starred, as thumbnails or a list.
import { h } from '../core.js';
import { resultList } from '../resultlist.js';
import { scopeBanner } from './categories.js';

export function favoritesView(root) {
  const el = h(`<div class="view fill"><div class="page-head"><div class="grow"><h1>Favourites</h1>
    <p>Star a photo in the viewer (or press F), or select files and choose Favourite.</p></div></div>${scopeBanner()}</div>`);
  root.append(el);
  const list = resultList({ filter: { fav: true }, sort: 'ts', order: 'desc', mode: 'grid', id: 'favorites', empty: 'No favourites yet' });
  el.append(list.el);
  return () => list.destroy();
}
