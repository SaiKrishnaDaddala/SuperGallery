# Maintainer release process

1. Update `app/features.py`, `compose.yaml`, the container smoke assertion, changelog and release notes to the intended version. Update documentation examples when appropriate.
2. Run the full tests, JavaScript checks and release-file audit. Review the staged diff, notices and generated image for private information. The automated guardrail does not replace human review.
3. Merge changes only after CI's test and fresh-container checks pass. Review dependency advisories; do not suppress findings without a documented assessment and fix plan.
4. Tag the reviewed commit with `vMAJOR.MINOR.PATCH` and push the tag. The tag workflow repeats validation, builds a source archive directly from committed Git objects, creates its SHA-256 checksum and publishes a GitHub release.
5. Verify the public archive, README links and fresh-install instructions. Announce only functionality actually validated. A GitHub release does not update running user installations.

Use patch versions for compatible fixes, minor versions for compatible features, and major versions for breaking changes. Document database migrations and rollback requirements. Do not silently move published tags; issue a new release for a correction.

CI uses pinned action commits and read-only permissions by default; only the release job gets repository write access. Pull requests do not receive publication credentials. Keep private vulnerability reporting and GitHub dependency/security notifications enabled.
