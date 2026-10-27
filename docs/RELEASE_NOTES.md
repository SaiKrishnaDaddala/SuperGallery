SuperGallery 2.4.0 is the first public source release: a NAS-hosted gallery with local photo/video search, people grouping, OCR, document search, smart albums and cleanup tools.

This release adds nine optional-feature switches and explicit remote HTTPS access settings, including compatibility with UGREEN gateways. Remote access requires authenticator verification. The default installation publishes HTTPS only and mounts the selected library read-only.

Download the source ZIP and check it against `SHA256SUMS`, or clone tag `v2.4.0`. Follow `docs/INSTALL.md`; the Docker build downloads and verifies pinned models. No credentials, user media, databases or deployment-specific configuration are included. No prebuilt container or native UGREEN package is provided in this release.

Existing installations: back up originals and private configuration before rebuilding. Read `docs/UPGRADING.md` for migration and rollback steps. The app does not update itself automatically.

Known scope: shared login rather than per-user NAS ACLs; CPU inference; sampled video frames rather than audio transcription; similarity and OCR can be wrong. ARM/GPU deployments and native UGREEN mobile catalog integration are not validated. Optional AWS celebrity lookup is off by default.

Report bugs and feature requests using the repository issue forms. Report vulnerabilities through GitHub's private security reporting, without posting sensitive data publicly.
