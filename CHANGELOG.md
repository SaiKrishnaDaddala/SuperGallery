# Changelog

## 2.6.0 — 2026-11-21

- New look in the style of Google Photos and Drive: a top bar with a large search box, a shorter sidebar (Home, Photos, Explore, People, Albums, Files; Free up space; More tools), an Upload button, pages on a white sheet, pill buttons, quieter titles and one style for every selection bar, dialog, menu and message. Dark mode follows the same design.
- Photos: the timeline groups photos by day inside each month, shows each photo at its own shape in rows that fill the width, and lets you select a whole day.
- Explore: a new page with People, Things and Collections.
- Things in photos: every photo that photo search has looked at is tagged with what is in it, from a list of more than 120 everyday things (people, pets, food, places, vehicles, documents, receipts…). Browse them in Explore, see them in the viewer's Info panel, and type a thing in search to find its photos. Tags come from the photo-search vectors already stored, so they cost almost no extra time; photos without a clear subject get no tags.
- Text recognition reads Hindi (Devanagari) and Telugu as well as English: lines the main reader is unsure of are read again with script-specific models (pinned by checksum and bundled in the image). Search readiness offers "Read all again" for photos read by earlier versions.
- Search: Hindi and Telugu words now match text inside photos and documents (they were split at vowel signs before). A new "Best match" order puts files whose name matches first, then people, folders and words inside, and is the default when you type words.
- Photo meaning search averages a few phrasings of your description, returns a fuller set of close matches and is about 3× faster: the library's vectors stay in memory while you search and are released after the idle time.
- File types: open one or more types on their own page, with list or thumbnail view, sorting and Select all; delete-all warns about personal files in the same dialog.
- File lists: one toolbar above the files with the count, Select all, sort and list/grid (remembered per page), loading placeholders instead of a spinner, and a Try again button when loading fails.
- Viewer: icon buttons like Google Photos; the Info panel lists the things in the photo.
- Lighter on the NAS: sign-in checks no longer take a database write lock on every request; the sidebar counts are cached between changes; regrouping similar photos is skipped when no photo changed; photo search decodes photos at the small size its model needs (about 3× less work per photo); thumbnails use at most half the cores.
- Security: pypdf 6.21.4 (fixes seven published vulnerabilities in PDF text extraction).
- Page titles match the menu (Home, Clean up, Collections, Storage, Recycle bin, Automation, Organize files, Library users) and technical wording was replaced.
- Recycle bin: shows only the selected user's deleted files. Restore all, Empty recycle bin and the sidebar count now stay inside that user too; before this, Empty recycle bin erased every user's deleted files whichever user was selected.
- Recycle bin: preview deleted photos and videos by clicking the thumbnail, double-clicking the row, or Preview in the selection bar. Previews are view-only.
- Double-click opens the preview in Collections, Similar photos, Duplicates and every other file list.
- Collections: Select all picks every file in the collection.
- Deleting, erasing, restoring and moving now show their progress, and then the result, in the middle of the screen while the page updates behind it. Keep working hides it and the task finishes in the corner.
- Selection bars in Recycle bin, Similar photos and Duplicates sit at the bottom of the screen, so the list no longer jumps under the pointer; the recycle bin forgets selected items once they are erased or restored.

## 2.5.0 — 2026-10-30

- People: select several people and merge them into one, choosing which name to keep.
- People: clicking a face opens all of that person's photos in the viewer, and the page updates as soon as a photo is deleted.
- People: when every photo of a person is deleted, the app says so and offers Recently deleted or Back to People; an old link to that person no longer shows an empty page.
- People: a named person whose photos are all deleted keeps the name until the recycle bin retention period ends, so restoring the photos brings them back under the same name. Unnamed groups are removed at once, and face data of deleted photos is always removed immediately.
- Restoring from the recycle bin finds faces again automatically; no manual "Find new faces" is needed.
- Search shows which person you are viewing, with the number of photos and a link back to them.
- The selection bar of file lists stays at the bottom of the screen while you scroll.
- Update notifications: the app checks the public GitHub release twice a day and shows a notice with the release notes and update steps. Turn it off in Settings → Updates or with `UPDATE_CHECK=0`. Optional one-click updates through a Watchtower container (`WATCHTOWER_URL`, `WATCHTOWER_TOKEN`), limited to the SuperGallery container.
- Phone: after the first message popup, taps on the left half of the screen no longer stop working; messages now sit just above the tab bar.
- Phone: page titles no longer squeeze into a narrow column next to their buttons.
- The update notice hides while a selection bar is open, so it never covers Delete.
- Smaller image: video thumbnails, length and frames use PyAV (FFmpeg libraries in a 35 MB wheel) in a time-limited helper process instead of Debian's ffmpeg package (about 135 MB less to download). The optional Amazon library is only installed with `--build-arg WITH_AWS=1`.
- Lower memory: AI models unload after 10 idle minutes (`MODEL_IDLE_MINUTES`) and freed memory is returned to the system; each database connection keeps an 8 MB cache and shares one memory-mapped view instead of 64 MB each.
- Gentler indexing: background work runs at lower CPU priority (`BACKGROUND_NICE`) and photo analysis uses half the cores by default.
- Faster People indexing: two photos are checked at once (`FACE_WORKERS`), about 1.8x faster in tests.
- Pages, scripts, styles and API data are gzip-compressed (about 3x smaller on first load); photos, videos and downloads are not.
- File details and text previews of a file deleted moments earlier return "not found" instead of a server error.
- Search results and other file lists show photo thumbnails again instead of folder icons.
- Sign-in animation also plays (calmer) when the device asks for reduced motion, with a remembered Pause/Play button.
- Private network IP addresses (10.x, 172.16–31.x, 192.168.x) work without adding them to ALLOWED_HOSTS.
- Duplicates: the recommended copy now recognises backup, download and chat folders by name (for example `Backups`, `MobileBackup`, `Downloads`, `WhatsApp Images`) and keeps the copy in camera or photo folders.
- Error messages from rejected requests are shown as readable text instead of "[object Object]".
- Dialogs close when you navigate away (for example with the browser Back button).
- Accessibility: descriptions for thumbnails, checkboxes, dropdowns and icon buttons; WCAG AA contrast for links, buttons, badges and secondary text in light and dark mode; keyboard access to similar-photo rows.
- Phone: larger touch targets for small links; the empty recycle bin message stays centred.
- Small sizes are rounded (no more "263.3333 B"); the unused ReDoc page is disabled.

## 2.4.0 — 2026-10-27

First public source release, based on the earlier private 2.3 application.

- Added nine instance-wide feature controls with server enforcement and safe indexing pause/resume behavior.
- Added explicit external HTTPS origin, exact trusted proxy configuration and a local-only remote-access switch.
- Fixed UGREEN Docker remote host rejection and HTTPS gateway handling while retaining mandatory remote MFA.
- Hardened recursive ZIP downloads to skip symlinks and excluded folders and recheck path boundaries.
- Added source installation, upgrades, rollback, privacy, security and contributor documentation; Apache-2.0 license with a NOTICE file crediting the original author, and third-party notices.
- Added pinned, checksum-verified model downloads, release checks, CI, issue forms and source release archives.
- Published tested multi-arch container images to `ghcr.io/saikrishnadaddala/supergallery` with SBOM and signed build provenance; `compose.yaml` now pulls the image, and `compose.build.yaml` builds from source.
- Added a strict Content-Security-Policy (scripts only from the app itself) and removed inline event handlers.
- Redesigned the sign-in screen with an animated backdrop of files sorting into folders (static when reduced motion is requested).

Existing functionality includes local photo/video search, OCR, document text, people groups with manual names, smart albums, file management, cleanup review, durable indexing and app-data backups. These capabilities were developed before the public release; earlier private versions are not published releases.
