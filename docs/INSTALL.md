# Install SuperGallery

## Requirements

- Linux host with Docker Engine and Docker Compose v2; a UGREEN NAS with Docker is suitable. x86-64 is tested; an arm64 image is published but less tested.
- A selected library directory and a separate persistent configuration directory.
- Internet access to pull `ghcr.io/saikrishnadaddala/supergallery` (or, when building from source, for Debian packages, Python dependencies and pinned models). No cloud account is required for local search.
- Start with a small test folder. Index size and runtime depend on your media, CPU and enabled features. Keep enough free storage for thumbnails, indexes and app backups. ARM/GPU deployments are not yet validated.

## Docker Compose

1. Download `compose.yaml` and `.env.example` from this repository into an empty folder (see the README), or clone the repository / a [release](https://github.com/SaiKrishnaDaddala/SuperGallery/releases).
2. Copy `.env.example` to `.env`. Set `NAS_HOST` to the exact local IP or hostname you will open. Set `LIBRARY_PATH` and `CONFIG_PATH` to existing absolute directories on the Docker host. Keep the configuration outside this source checkout and outside the library.
3. Leave `LIBRARY_MODE=ro` for the first run. This permits viewing and indexing but prevents uploads, renames, moves and deletion in the library. App data still needs a writable configuration mount.
4. Run `docker compose config --quiet` to check configuration, then `docker compose up -d`. This pulls the tested image from GHCR. To build from source instead, use `docker compose -f compose.yaml -f compose.build.yaml up -d --build`; the build downloads models and stops on any checksum mismatch.
5. Open `https://YOUR_NAS_HOST:8843`. Replace the host and, if changed, port with your configured values. Wait for startup to finish; inspect `docker compose logs --tail=100` locally if necessary.
6. Verify the certificate belongs to your NAS before trusting it, create a strong password in the browser, and enable authenticator verification in Settings. Store recovery codes somewhere safe outside the NAS.
7. Start a library scan. In Settings, choose your optional features and start the indexes you need. First indexing is CPU intensive; progress and cancellation are available. Search quality improves as indexing completes.

The default certificate is generated locally and is not publicly trusted. For managed certificates, mount your certificate and key read-only and set `TLS_CERT_FILE` and `TLS_KEY_FILE` to their container paths. Protect the key. A public reverse proxy must present a valid certificate for its domain. Do not disable TLS verification in clients as a permanent solution.

## UGREEN Docker interface

1. Install Docker from the NAS App Center.
2. Create a dedicated project folder on the NAS. Only `compose.yaml` and your private `.env` are needed; the image is pulled from GHCR.
3. Prepare `.env` next to `compose.yaml` using the NAS's actual folder paths. If the project editor cannot read an adjacent `.env`, replace the `${...}` expressions in a private copy of the Compose file with those values. Never publish that private configuration.
4. In Docker → Project, create a project from that folder and its Compose file, then deploy. UI labels vary by UGOS version. Review the deployment log for a successful pull and startup. To update later, redeploy the project (it pulls `latest` again) or pull the image under Docker → Image.
5. Open the local HTTPS address directly in a browser and complete setup. The Docker web shortcut may choose HTTP unless configured for the HTTPS port; MFA needs HTTPS.

This is a Docker app, not a signed native UGREEN package. A desktop shortcut or mobile browser bookmark does not add it to the UGREEN mobile app catalog.

## Enable file changes deliberately

Back up the originals first. Set `LIBRARY_MODE=rw` and redeploy if you want uploads or file operations. Enable the related features in Settings. Trash is stored in `.supergallery_trash` inside the library and is purged after `TRASH_RETENTION_DAYS` (default 30 days). Turning off cleanup suggestions does not stop ordinary file operations or trash retention.

Mount only folders that every person with the application password may access. The app runs as the container user (root by default for NAS compatibility), so the Docker mount is the access boundary. The supplied Compose drops capabilities and enables `no-new-privileges`, but does not implement per-user filesystem ACLs. Advanced installations can set a tested UID/GID and grant it access to the configuration and intended folders.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Invalid host header | Add the exact local hostname/IP to `ALLOWED_HOSTS`; for external access use the Remote access settings. Never use `*`. |
| Certificate warning | Check the hostname and certificate against your NAS; configure a trusted certificate where possible. |
| No search results | Scan first, then start the relevant index; check task errors and supported formats. |
| Cannot upload or move files | The default library mount is read-only; check mount mode and filesystem permissions. |
| Remote MFA asks for HTTPS | Verify the public HTTPS URL, proxy peer and protocol forwarding; see [remote access](REMOTE_ACCESS.md). |
| Changed `.env` but no effect | Recreate the container with `docker compose up -d`; a restart alone does not update environment variables. |
| Startup is slow after an upgrade | A pre-upgrade app-data backup may run before HTTPS startup; check logs and disk space. |

Do not use `docker compose down -v` as a troubleshooting shortcut. Retain the configuration directory and your independent media backups.
