SuperGallery 2.6.0 is a big redesign: it now looks and works like Google Photos and Drive, recognises things in your photos, reads Hindi and Telugu text, and is lighter on your NAS.

## A new look
- **Google-style design:** a top bar with a large search box, a short sidebar, an Upload button, clean white pages and rounded buttons. Dark mode included.
- **Photos timeline** grouped by day, with every photo at its own shape. Hover a date to select the whole day.
- **Explore:** People, Things and Collections on one page.
- **One toolbar for every file list:** count, Select all, sort, and list or thumbnail view (remembered).
- **File types** open on their own page, as a list or thumbnails.

## Smarter
- **Things in photos:** dogs, food, temples, receipts, beaches and more than 120 other everyday things are recognised on your NAS. Find them in Explore, in the photo's Info panel, or just type "dog" in search.
- **Hindi and Telugu text** in photos and scans is now read and searchable. Photos read by earlier versions can be read again from Search → Search readiness → Read all again.
- **Best match first:** typing words in search shows the best matches first.
- **Photo search** is about 3× faster and returns a fuller set of close matches.

## Recycle bin
- Shows only the deleted files of the person you selected at the top, and Empty recycle bin / Restore all stay inside that person. **Before this update, Empty recycle bin erased every person's deleted files.**
- Preview deleted photos: click the thumbnail or double-click the row.

## Smoother everyday use
- Deleting, erasing, restoring and moving show progress and the result in the middle of the screen.
- Double-click opens the preview in every list; selecting no longer makes the list jump.
- Collections have Select all.

## Lighter on your NAS
- Fewer database locks per request, cached counts, no needless regrouping of similar photos, and less decoding work when indexing photos.

## Install or update
Use `ghcr.io/saikrishnadaddala/supergallery:2.6.0` (or `:latest`). On a UGREEN NAS: Docker → Project → supergallery → Redeploy, tick "Pull the latest image". With Docker Compose: `docker compose pull && docker compose up -d`. Your library, people, albums and settings are kept. After the update, things in photos are recognised automatically the next time photo search indexes (it reuses existing work, so it is quick).
