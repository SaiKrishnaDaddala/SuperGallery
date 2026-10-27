# Choose your features

Open Settings → Features. Switches apply to the entire instance and are enforced by the server as well as the interface. They are preferences for people sharing one login, not role permissions.

| Control | Effect when off |
| --- | --- |
| Photo meaning | Blocks natural-language photo search and its indexing jobs |
| Video scenes | Blocks scene search and sampled-frame indexing |
| Document text | Stops document indexing and excludes extracted document text from search |
| Text recognition | Stops OCR and excludes recognized text from search |
| People | Hides face groups and names, blocks face indexing and people filters |
| Smart albums | Hides and blocks saved search albums |
| Uploads | Blocks both upload APIs, upload controls and drag/drop |
| Duplicate and cleanup tools | Hides cleanup recommendations and blocks cleanup review APIs; new full scans skip duplicate hashing/similarity stages |
| Cleanup automation | Stops scheduled cleanup rules; also requires cleanup tools to be enabled |

All capabilities remain available by default for compatibility. Indexing is explicitly started by the user. Turning a feature off requests cancellation of its running jobs and pauses queued work; a currently executing item may finish. Re-enabling does not automatically restart indexes. Start or resume them from Settings.

Turning a feature off does **not** delete originals, existing indexes, face names or albums. They become available again when enabled. It is not an erasure mechanism: sensitive derived information remains in configuration backups until you remove those backups separately. File names and paths remain searchable.

Authentication, app-data backups and basic file browsing cannot be disabled through these switches. Turning cleanup tools off does not disable normal file deletion or the configured trash-retention purge. Use a read-only Docker mount when you want a filesystem-enforced viewing-only library.
