<p align="center">
  <img src="web/icons/icon.svg" width="112" height="112" alt="SuperGallery icon">
</p>

<h1 align="center">SuperGallery</h1>

![SuperGallery — Your memories. On your NAS.](docs/screenshots/social-preview.jpg)

<p align="center"><a href="#quick-start"><b>Get started with Docker</b></a> · <a href="https://github.com/SaiKrishnaDaddala/SuperGallery/discussions">Ask a setup question</a> · <a href="docs/SHARING.md">Share SuperGallery</a></p>

<p align="center">
  <b>Your photos, videos and files — searchable, sorted and cleaned up, on your own NAS.</b><br>
  Created by <a href="https://github.com/SaiKrishnaDaddala">Sai Krishna Daddala</a>
</p>

<p align="center">
  <a href="https://github.com/SaiKrishnaDaddala/SuperGallery/actions/workflows/ci.yml"><img src="https://github.com/SaiKrishnaDaddala/SuperGallery/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://github.com/SaiKrishnaDaddala/SuperGallery/pkgs/container/supergallery"><img src="https://img.shields.io/badge/docker-ghcr.io-2496ED?logo=docker&logoColor=white" alt="Docker image"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache-2.0 license"></a>
</p>

<p align="center">
  <a href="#quick-start">Install</a> ·
  <a href="#features">Features</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="docs/UPGRADING.md">Upgrade</a> ·
  <a href="https://github.com/SaiKrishnaDaddala/SuperGallery/issues/new?template=bug.yml">Report a bug</a> ·
  <a href="https://github.com/SaiKrishnaDaddala/SuperGallery/issues/new?template=feature.yml">Request a feature</a> ·
  <a href="SECURITY.md">Security</a>
</p>

![SuperGallery sign-in screen](docs/screenshots/login.jpg)

SuperGallery is a self-hosted photo gallery and smart file manager for a home NAS (built and tested on UGREEN, runs anywhere Docker does). It indexes the folders you choose, finds what you remember with on-device AI search, groups people and look-alike shots, and helps you reclaim space from duplicates, screenshots and forwarded memes — without uploading anything to a cloud service.

*All screenshots use a generated demo library (`tools/make_demo_library.py`); no personal media is shown.*

## Features

### Gallery and search
- **Photos timeline** grouped by month with a year/month scrubber, adjustable grid size and a full-screen viewer for photos, videos, audio and PDFs.
- **Search by meaning** — type "sunset at the beach" or "people cycling" and get matching photos, using a local CLIP model (no cloud).
- **Video scene search** — finds the moment inside a video and opens it at that timestamp.
- **Text in images and documents** — on-device OCR for receipts and screenshots, plus text extraction from PDFs and office documents.
- **People** — local face grouping with names you assign.
- **Smart albums** that keep themselves up to date from a saved search.
- **Command palette** (Ctrl K) and search filters such as `type:video larger:100mb after:2025-01-01`.

### File manager
- Keyboard-driven, dual-pane file manager with list and grid views that stay fast with 100,000+ entries: previews, multi-select, drag-and-drop moves, rename, bulk rename with preview and new folders.
- **Resumable uploads** of very large files with checksums, plus ZIP download of folders.
- **Recently deleted** recycle bin with restore and configurable retention — deletes are never immediate.
- Per-user libraries: pick one person, several, or everyone; duplicates are judged within each person's own files.

### Cleanup and storage
- **Duplicates** — exact copies found by content hash, with "keep the recommended copy", "prefer keeping files in…" and a safety lock that always keeps one copy.
- **Similar photos** — burst shots, resized and re-saved copies grouped together; keep the best, remove the rest.
- **Collections** — automatic categories: camera photos, WhatsApp/chat images and memes, screenshots, documents and receipts, low quality, blurry, dark and more.
- **Review** — the best clean-up suggestions in one place, including recommendations learned from what you deleted before.
- **Storage insights** — space by type, top extensions, size distribution, largest files, duplicate folders and delete-by-extension.
- **Cleanup rules** (optional) that run on a schedule.

### Built for a NAS
- Fast incremental scans and background indexing with progress, pause and cancel; built to handle large libraries.
- Installable as an app (PWA) on desktop and phone, with a light and dark theme and a phone layout with tab bar.
- Nine feature switches so you only run what you need.
- App-data backup and restore from Settings.

### Security
- Password sign-in with optional authenticator codes (TOTP) and one-time recovery codes; revocable sessions.
- HTTPS by default with a locally generated certificate, host allow-list, CSRF protection and a strict Content-Security-Policy.
- Local-network only by default; remote access must be switched on deliberately and requires two-step verification.
- Library mounted read-only on first run; the container drops all Linux capabilities.

See [feature controls](docs/FEATURES.md), [privacy](docs/PRIVACY.md) and [remote access](docs/REMOTE_ACCESS.md) for details. Optional celebrity lookup uses Amazon Rekognition, is off by default and is not part of the standard image (build with `--build-arg WITH_AWS=1`); every other feature works fully offline.

## Screenshots

![Library overview](docs/screenshots/library.jpg)

| Sign in | Photos |
| --- | --- |
| ![Sign-in screen with files sorting into folders](docs/screenshots/login.jpg) | ![Photos timeline](docs/screenshots/photos.jpg) |
| **Duplicates** | **Similar photos** |
| ![Duplicate finder with smart select](docs/screenshots/duplicates.jpg) | ![Similar photos grouped](docs/screenshots/similar.jpg) |
| **Collections** | **Storage insights** |
| ![Automatic photo and video categories](docs/screenshots/collections.jpg) | ![Storage insights and suggestions](docs/screenshots/storage.jpg) |
| **File manager** | **File types** |
| ![Dual-pane file manager with folder sizes](docs/screenshots/files.jpg) | ![Space by extension with bulk select](docs/screenshots/file-types.jpg) |
| **Search** | **Review** |
| ![Search by name, text and filters](docs/screenshots/search.jpg) | ![Review suggestions](docs/screenshots/review.jpg) |
| **Upload** | **Settings** |
| ![Resumable uploads](docs/screenshots/upload.jpg) | ![Security and feature settings](docs/screenshots/settings.jpg) |

**Dark mode**

| Sign in | Library | Duplicates |
| --- | --- | --- |
| ![Sign-in in dark mode](docs/screenshots/login-dark.jpg) | ![Library in dark mode](docs/screenshots/library-dark.jpg) | ![Duplicates in dark mode](docs/screenshots/duplicates-dark.jpg) |

**On your phone**

<p>
  <img src="docs/screenshots/mobile-library.jpg" alt="Library on a phone" width="240">
  <img src="docs/screenshots/mobile-photos.jpg" alt="Photos on a phone" width="240">
  <img src="docs/screenshots/mobile-duplicates.jpg" alt="Duplicates on a phone" width="240">
</p>

## Quick start

You need a Linux host with Docker and Docker Compose v2 — a UGREEN (or other) NAS with Docker works well. Images are published for **x86-64** (tested) and **arm64**.

Every change that passes the test suite is published as `ghcr.io/saikrishnadaddala/supergallery:latest`; releases also get version tags such as `:2.4.0`. You only need two files:

```sh
mkdir supergallery && cd supergallery
curl -fsSLO https://raw.githubusercontent.com/SaiKrishnaDaddala/SuperGallery/main/compose.yaml
curl -fsSL https://raw.githubusercontent.com/SaiKrishnaDaddala/SuperGallery/main/.env.example -o .env
# Edit .env: NAS_HOST, LIBRARY_PATH and CONFIG_PATH must match your machine.
docker compose up -d
```

Open `https://YOUR_NAS_HOST:8843`, check the certificate, create your password and turn on two-step verification in Settings. There are no default credentials. Then start a scan.

**Update to the latest version at any time:**

```sh
docker compose pull && docker compose up -d
```

On UGREEN, create a project in **Docker → Project** from `compose.yaml` and redeploy it to update. The [installation guide](docs/INSTALL.md) covers UGREEN step by step, certificates and enabling file changes. To build from source instead: `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

## One-click updates (optional)

SuperGallery tells you when a new version is out (Settings → Updates). By itself it cannot replace its own container,
because it has no access to Docker, on purpose. To get an **Update** button that installs the new version for you,
add the maintained [Watchtower](https://github.com/nicholas-fedor/watchtower) container to `compose.yaml`. It only
acts when you press Update, and only on the `supergallery` container:

```yaml
services:
  supergallery:
    # ...existing settings, plus:
    environment:
      WATCHTOWER_URL: "http://watchtower:8080"
      WATCHTOWER_TOKEN: "${WATCHTOWER_TOKEN:?Set WATCHTOWER_TOKEN in .env}"

  watchtower:
    image: nickfedor/watchtower:latest
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      WATCHTOWER_HTTP_API_UPDATE: "true"
      WATCHTOWER_HTTP_API_PERIODIC_POLLS: "false"
      WATCHTOWER_HTTP_API_TOKEN: "${WATCHTOWER_TOKEN:?Set WATCHTOWER_TOKEN in .env}"
```

Put a long random `WATCHTOWER_TOKEN` in `.env` (for example the output of `openssl rand -hex 32`). Do not publish
Watchtower's port: it has full control of Docker and should only be reachable by SuperGallery on the project network.

## Tuning for your NAS

These optional environment variables go in `compose.yaml`; the defaults suit a 4–8 core NAS.

| Variable | Default | What it does |
| --- | --- | --- |
| `ANALYZE_WORKERS` | half the cores (2–4) | Photos analysed at once during indexing |
| `FACE_WORKERS` | `2` | Photos checked for faces at once (People) |
| `HASH_WORKERS` | `4` | Files read at once when finding duplicates |
| `BACKGROUND_NICE` | `10` | CPU priority of indexing (0 = same as the web UI, 19 = lowest) |
| `MODEL_IDLE_MINUTES` | `10` | Unload the AI models after this many idle minutes to free memory (0 = keep loaded) |

## Good to know

- One shared login sees all mounted folders. Per-person filters organize the library; they are not separate accounts. Mount only what everyone may see.
- Keep an independent backup of your originals. Clean-up actions go to the recycle bin first, but review before you delete.
- Not affiliated with UGREEN or Apple. This is a Docker web app, not a native UGREEN package.

## Updates and contributing

Releases come with source archives, SHA-256 checksums and container images with signed build provenance (`gh attestation verify oci://ghcr.io/saikrishnadaddala/supergallery:latest --owner SaiKrishnaDaddala`). The app never updates itself; see [upgrading](docs/UPGRADING.md).

Have an idea? [Request a feature](https://github.com/SaiKrishnaDaddala/SuperGallery/issues/new?template=feature.yml) — suggestions are welcome. Found a problem? [Report a bug](https://github.com/SaiKrishnaDaddala/SuperGallery/issues/new?template=bug.yml) (never attach personal media, passwords, `.env` or databases). Security problems: please use [private vulnerability reporting](https://github.com/SaiKrishnaDaddala/SuperGallery/security/advisories/new) instead of a public issue — see [SECURITY.md](SECURITY.md).

Pull requests are welcome; start with [CONTRIBUTING.md](CONTRIBUTING.md) and the [architecture notes](docs/ARCHITECTURE.md).

## Credits

**SuperGallery was created and is maintained by [Sai Krishna Daddala](https://github.com/SaiKrishnaDaddala).**

If you use, fork, modify or redistribute SuperGallery, keep the [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) files and credit the original project, for example: *"Based on SuperGallery by Sai Krishna Daddala"* with a link to this repository.

SuperGallery stands on great open-source work — CLIP, OpenCV Zoo face models, RapidOCR, PyAV/FFmpeg, FastAPI, Pillow, Lucide icons and more. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

Copyright 2026 Sai Krishna Daddala. Licensed under the [Apache License 2.0](LICENSE). Redistributions and derivative works must retain the copyright notice and the attribution in [`NOTICE`](NOTICE). Third-party models, libraries and system packages keep their own licenses.
