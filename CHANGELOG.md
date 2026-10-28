# Changelog

## Unreleased

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
