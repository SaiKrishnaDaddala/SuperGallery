# Architecture

SuperGallery is a single-process FastAPI application with a plain JavaScript frontend. `app.serve` starts HTTPS plus an internal HTTP compatibility listener sharing the application. Use one application worker: in-memory task coordination is not designed for multiple independent workers.

| Area | Main modules |
| --- | --- |
| Request security | `auth_http.py`, `security.py`, `network.py` |
| Feature controls | `features.py`, `web/js/features.js` |
| File metadata and browsing | `db.py`, `scanner.py`, `queries.py`, `fileops.py` |
| Search and people | `visual_search.py`, `search_index.py`, `ocr_index.py`, `people.py` |
| Background work | `jobs.py`, `intelligence_tasks.py` |
| Saved searches and recovery | `albums.py`, `backups.py` |
| Browser interface | `web/js`, `web/css`, `web/index.html` |

SQLite stores the index and application metadata in the persistent configuration mount. Original files stay in mounted library directories. The durable intelligence queue records work across restarts; each feature gate is checked again before jobs resume. Optional capability gates apply at API boundaries and search-source selection, not only navigation rendering.

Local inference uses ONNX CLIP for image/text similarity, OpenCV YuNet/SFace for face detection and embeddings, and RapidOCR for text recognition. Video search indexes sampled frames. Outputs are fallible suggestions; identity and activity labels are not ground truth.

The frontend calls same-origin APIs. A reverse proxy must preserve the configured Host and establish trusted external HTTPS semantics. No arbitrary forwarded client address is accepted for rate limiting. The shared-login design deliberately does not claim per-NAS-user ACL integration.
