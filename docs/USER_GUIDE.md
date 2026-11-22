# Using SuperGallery

A short guide to everyday use. For installing and updating, see [INSTALL.md](INSTALL.md) and [UPGRADING.md](UPGRADING.md).

## Finding your way around

- **Search box (top):** type a name, a word that appears in a document or screenshot, a person's name, a thing ("dog", "receipt") or a place ("Hyderabad"). Press Enter for the full search page. `Ctrl K` opens search and commands from anywhere.
- **Whose files (top right):** pick one person, several, or All users. Every page, count and action then stays inside the people you picked. This is a filter, not a separate login: everyone signed in with the app password can switch it.
- **Menu (left on a computer, bottom tabs on a phone):** Home, Photos, Explore, People, Albums, Favourites and Files; then Free up space (Clean up, Duplicates, Similar photos, Large files, File types); More tools; Storage, Recycle bin and Settings at the bottom. On a phone, the menu button at the top left shows every page.

## Photos

- **Photos** shows everything by month and day. Hover a date (or use **Select**) to pick a whole day. The slider changes the photo size; the years on the right jump through time.
- **Open a photo:** click it (Photos) or double-click it (any other list). In the viewer: arrows move between photos, **i** shows details (including things recognised in the photo), **F** adds it to Favourites, **Delete** moves it to the Recycle bin.
- **Favourites:** the star in the viewer, or select photos and choose **Favourite**. All of them are under **Favourites** in the menu.
- **On this day** on Home shows photos taken on today's date in earlier years.

## Explore

- **People:** faces are grouped on your NAS. Add names, merge groups that are the same person (Select → pick → Merge), and fix mistakes from a person's page. SuperGallery joins groups that are clearly one person by itself; when it is not sure, **Same person?** at the top asks you (your answer is remembered). Faces seen in only one photo are tucked away; the note under the groups shows them.
- **Things:** more than 130 everyday things (pets, food, temples, gods and idols, pooja, events, vehicles, receipts and more) recognised in photos after **Photo meaning** has looked at them. Matches can be imperfect.
- **Places:** where photos were taken, from the location the camera or phone saved in the photo. Names come from a list of towns stored with the app; nothing is sent to a map service. New places appear after a library scan.
- **Collections:** photos sorted automatically: camera photos, WhatsApp and chat images, screenshots, documents, blurry, dark and more.

## Search

- **Files & text** finds names, folders, people, places, things, and words inside documents, screenshots and scanned pages (English, Hindi and Telugu). **Best match** puts the closest results first.
- **Photo meaning** finds photos by description: "kids playing in the rain", "birthday cake".
- **Video scenes** finds the moment inside a video.
- Filters: `type:video`, `larger:100mb`, `after:2025-01-01`, `person:"Name"`. **Save search** turns a search into an album that keeps itself up to date.
- Photos read before version 2.6 can be read again for Hindi and Telugu: Search → **Search readiness** → **Read all again** (this takes a while on big libraries).

## Files

A file manager for everything on the NAS: list or thumbnails, previews, select many, move, copy, rename (also many at once), zip, download and new folders. **File types** shows space by type; **Open** shows all files of a type on their own page.

## Free up space

- **Clean up** collects the safest suggestions (extra duplicate copies, phone recycle-bin leftovers, thumbnail caches, system junk, unfinished downloads, empty files). Home shows the total with **Clean up now**.
- **Duplicates** and **Similar photos** let you keep the best copy and remove the rest; one copy of every file is always kept.
- Nothing is erased straight away: deleted files go to the **Recycle bin** first and can be restored until the retention period ends (30 days by default).

## Recycle bin

Shows the deleted files of the people picked at the top. Click a thumbnail to preview, select to **Restore** or **Delete forever**. **Empty recycle bin** and **Restore all** only touch the people picked at the top.

## Share links

1. Select photos or videos anywhere (Photos, a collection, search results, an album) and choose **Share link**.
2. Give it a name and choose how long it works: 1 day, 1 week or 30 days.
3. Copy the link and send it. Anyone with it can view and download those photos without an account — nothing else in your library.

Turn a link off any time in **Settings → Shared links**. Create links while you are using an address the other person can reach (for example your UGREENlink address); a link made on your home-network address only works inside your home. For your privacy the NAS keeps only a fingerprint of each link, so copy it when it is shown.

## Back up a phone

Open **Upload** on the phone, choose a backup folder once, then **Choose photos to back up** and pick your recent photos (or everything). Photos already on the NAS for that person are skipped, so it is safe to pick the same ones again. Keep the page open until uploads finish. Browsers cannot back up automatically in the background, so open the page again to back up new photos.

## Settings worth knowing

- **Security:** turn on two-step verification (needed for access from outside your home) and sign out other sessions.
- **Features:** switch off tools you do not use so they stop indexing.
- **Updates:** SuperGallery tells you when a new version is out; to update on a UGREEN NAS use Docker → Project → supergallery → Redeploy with "Pull the latest image".
- **Shared links:** see and turn off share links.
