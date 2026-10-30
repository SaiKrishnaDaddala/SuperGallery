SuperGallery 2.5.0 makes People easier to manage, tells you when a new version is out, and runs lighter on your NAS.

## People
- **Merge people in one step:** tap Select on the People page, pick the groups that are the same person and choose which name to keep.
- **Browse a person's photos** in the viewer, one after another, straight from their page.
- **Deleting is smoother:** pages update right away, the selection bar stays at the bottom of the screen, and when every photo of someone is deleted the app says so and takes you back.
- **Names survive a restore:** if you restore a named person's photos from Recently deleted, they come back under the same name automatically.

## Updates
- A notice appears when a new version is available, with these release notes and the steps to update. You can turn the check off in Settings.
- Optional one-click updates with Watchtower (see the README).

## Faster and lighter
- About 27% smaller download (416 MB instead of 567 MB).
- Uses less memory: AI models unload after 10 idle minutes.
- Indexing runs at lower priority so your NAS stays responsive, and finding people is about 1.8x faster.
- Pages load about 3x less data.

## Fixes and polish
- On phones, taps on the left side of the screen stopped working after the first message popup. Fixed, and page titles no longer get squeezed next to their buttons.
- Readable error messages, aligned pages, working File types selection, photo thumbnails in search results, a calmer sign-in animation for reduced-motion devices with a pause button, and many accessibility improvements.
- Duplicate cleanup recognises backup, download and WhatsApp folders, so it keeps your originals.

## Install or update
Use `ghcr.io/saikrishnadaddala/supergallery:2.5.0` (or `:latest`). On a UGREEN NAS: Docker → Project → supergallery → Redeploy, tick "Pull the latest image". With Docker Compose: `docker compose pull && docker compose up -d`. Your library, people, albums and settings are kept.
