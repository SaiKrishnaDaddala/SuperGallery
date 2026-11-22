SuperGallery 2.8.0 makes People and Things much more accurate on real family libraries.

## Better
- **One person, one group:** if someone was split into several groups (with and without glasses, different years), SuperGallery now brings the groups back together by itself. It never joins two faces from the same photo, two different names, or groups from different users' libraries.
- **"Same person?":** when two groups look alike but SuperGallery is not sure, People asks you. Your answer is remembered.
- **Fewer strangers in People:** faces seen in only one photo (often people in a crowd) are tucked away; a note at the bottom shows them if you want.
- **Things you actually photograph:** new things for gods and idols, pooja, public events, portraits, greeting cards, ads, emails and spreadsheets, and stricter Temple, Certificate and ID card. Temple no longer collects every function with garlands.
- **Faster Places:** WhatsApp images and screenshots are skipped when looking for locations.
- **Tidier empty pages:** empty messages sit in the middle of the page; empty Albums offers a search.

New to SuperGallery? The [user guide](https://github.com/SaiKrishnaDaddala/SuperGallery/blob/main/docs/USER_GUIDE.md) walks through every page.

## Install or update
Use `ghcr.io/saikrishnadaddala/supergallery:2.8.0` (or `:latest`). On a UGREEN NAS: Docker → Project → supergallery → Redeploy, tick "Pull the latest image". With Docker Compose: `docker compose pull && docker compose up -d`. Your library, people, names, albums and settings are kept. After the update, SuperGallery re-tags Things and brings split People groups together by itself in the background (a few minutes on a large library).

---

Earlier release notes:

SuperGallery 2.7.1 is a small fix on top of 2.7.0: right after an update, while the NAS prepares its database (a few minutes on large libraries), the app now says it is finishing the update instead of showing errors.

SuperGallery 2.7.0 adds Favourites, On this day, Places, share links and phone backup, and makes People groups better as they grow.

### New
- **Favourites:** tap the star in the viewer (or press F), or select photos and choose Favourite. Find them all under Favourites in the menu.
- **On this day:** Home shows photos from today's date in earlier years.
- **Places:** where your photos were taken, named on your NAS from each photo's location. Browse them in Explore or type a town in search. No map service is used and nothing leaves your NAS.
- **Share links:** select photos or videos, choose Share link, and send the link to anyone. It works without signing in for 1 day, 1 week or 30 days, shows only those photos, and can be turned off any time in Settings → Shared links.
- **Back up this phone:** on the Upload page, pick photos from your phone; ones already on your NAS are skipped.
- **Free up space on Home:** see how much Clean up can free and do it in one tap. Everything goes to the Recycle bin first.

### Better
- **Two-step verification** changes take effect immediately.
- **Phones and tablets:** File types and the photo viewer fit small screens better.
- **People groups improve as they grow:** each person is matched against all of their faces, not just the first one, so the same person no longer splits into several groups as they age or the light changes.

New to SuperGallery? The [user guide](https://github.com/SaiKrishnaDaddala/SuperGallery/blob/main/docs/USER_GUIDE.md) walks through every page.

### Install or update
Use `ghcr.io/saikrishnadaddala/supergallery:2.7.1` (or `:latest`). On a UGREEN NAS: Docker → Project → supergallery → Redeploy, tick "Pull the latest image". With Docker Compose: `docker compose pull && docker compose up -d`. Your library, people, albums and settings are kept. Places appear after the next library scan (Settings → Rescan now). The first start after updating a large library can take a few minutes while the database is prepared.
