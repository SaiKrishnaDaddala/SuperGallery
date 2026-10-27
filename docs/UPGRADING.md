# Upgrade and recovery

`latest` is rebuilt from `main` only after the full test suite and container smoke test pass. To stay on a specific release, set `SUPERGALLERY_TAG` in `.env` (for example `2.4.0`). Review the changelog and any migration notes first. The app never updates your running NAS by itself.

## Before changing versions

1. In Settings, pause indexing and wait for file operations to finish.
2. Create and verify an app-data backup, then download it to another device. This snapshot includes the index, names, albums and application preferences. It does **not** include original files, login credentials, TLS keys or remote-access configuration.
3. Maintain a separate backup of your original library. To capture complete configuration for rollback, stop the container and back up the entire `CONFIG_PATH` directory using your NAS backup tools. This contains secrets: encrypt it and restrict access. Do not attach it to an issue.
4. Keep `.env` and private Compose overrides outside public Git history. Keep `CONFIG_PATH` outside the source directory.

## Image installation (recommended)

```sh
docker compose pull
docker compose up -d
docker compose logs --tail=100
```

Compose keeps your `/config` volume, so the index, settings and login survive the update. Confirm the version in Settings, sign in, check your library, and start/resume the indexes you want. Changed mount paths require a fresh scan.

To roll back, set `SUPERGALLERY_TAG` to the previous release in `.env`, then run the same commands. Restore the pre-upgrade configuration backup if the newer version migrated data.

## Git installation (build from source)

```sh
docker compose stop
git fetch --tags origin
git checkout v2.4.0
docker compose -f compose.yaml -f compose.build.yaml config --quiet
docker compose -f compose.yaml -f compose.build.yaml up -d --build
docker compose logs --tail=100
```

Replace the example tag with the version you intend to install. If you have local source changes, preserve them before checkout; do not use a destructive reset.

## Download / UGREEN Docker installation

Redeploy the project; with `pull_policy: always` it fetches the newest image for the configured tag. Keep the pre-upgrade configuration backup until validation is complete. Projects created from an older source-build `compose.yaml` should switch to the current `compose.yaml`, keeping the same config and library mounts.

Checksums detect corrupted or substituted files relative to the published checksum file. They are not an independent signature of the publisher.

## Rollback

Do not assume an older image can read a newer database schema. Stop the new container, restore the complete pre-upgrade configuration copy to its original path, select the previous source tag/image, and redeploy with the same mounts. Keep the failed configuration separately for diagnosis. Never overwrite or restore originals as part of an app-index rollback.

The app's built-in restore replaces app metadata after restart, preserves current trash/deletion records, clears cleanup rules, pauses queued intelligence jobs and triggers a rescan. It does not undo filesystem operations or restore credentials. Downloaded app-data archives are portable backups for operator recovery; the current UI restores snapshots already present in the configured backup directory and does not provide an archive-upload wizard.
