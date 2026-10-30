# Privacy and data handling

SuperGallery reads only directories mounted into its container, but everyone with the shared app login can access those directories. Owner filters do not provide authorization boundaries.

## Stored locally

- File paths, names, timestamps, dimensions and duplicate-analysis metadata.
- Thumbnails and sampled video previews.
- Search embeddings, extracted document text and OCR text.
- Face embeddings, face crops, group assignments and manually entered names. Deleting a photo removes its faces at once; a named person whose photos are all deleted keeps only their name and one face signature for the recycle-bin period (so a restore brings the name back), then is removed.
- Smart albums, preferences, task state, trash records and app-index backups.
- Password verifier, encrypted authenticator state, session/recovery-code records and TLS material in the private configuration directory.

Face data and search indexes can reveal private information even when original files are elsewhere. Protect `/config` and all its backups. The application does not encrypt the entire media library or index at rest; use NAS storage encryption and appropriate permissions if needed.

## Network activity

The Docker build downloads operating-system packages, Python dependencies and pinned public models. Core photo search, OCR, document search and face grouping run on the host. There is no required cloud account or application analytics service. Your browser and configured gateway still make their normal network connections; a remote gateway can process traffic and metadata.

Update checks read only the public latest-release page of the GitHub repository, twice a day; nothing about your library is sent. Turn them off in Settings → Updates or with `UPDATE_CHECK=0`.

Optional celebrity suggestions require an image built with `--build-arg WITH_AWS=1`, `CELEBRITY_MATCHING_ENABLED=1` plus separately configured AWS credentials/region. They send a selected face image to Amazon Rekognition when requested and may incur AWS charges. The default is off. Review the provider's terms and data handling before enabling it. There is no automatic identity guarantee, and suggested names need human review.

## Removal and backups

Feature switches hide and stop optional functionality; they do not erase previously derived data or its backups. App-data backups exclude original media and credentials but still contain sensitive indexes and names. Deleting a file through a writable library normally moves it into the app trash; retention and explicit purge can permanently remove it. Use independent backups.

Never publish configuration, databases, thumbnails, real face crops, personal screenshots, certificates' private keys, credentials or unredacted logs. Bug reports should use synthetic examples and redact local addresses and private file paths.
