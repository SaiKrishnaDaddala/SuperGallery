# Contributing

Bug reports and feature proposals are welcome through the issue forms. Explain the problem and the desired outcome; use synthetic examples. For larger changes, discuss the design in an issue first.

## Development

Use Python 3.12, Node.js 22 or later for JavaScript syntax checks, and FFmpeg for media previews. A Linux environment matches deployment most closely.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export CONFIG_DIR="$PWD/.test-config"
export ALLOWED_HOSTS=localhost,127.0.0.1
export SCAN_ROOTS="$PWD/sample-library"
python tools/make_sample.py "$PWD/sample-library"
python tools/download_models.py
python -m app.serve
```

Keep development libraries synthetic and configuration out of Git. The model downloader can verify existing files with `--verify-only`. Unit tests use small synthetic fixtures and mock model inference where appropriate; passing them is not a model-quality benchmark.

```sh
CONFIG_DIR="$PWD/.test-config" python -m pytest -q
python tools/check_release.py
find web/js -name '*.js' -exec node --check {} \;
```

Before submitting, run relevant tests and explain the behavior change and validation in your pull request. Include regression tests for security boundaries, file operations and task persistence. UI changes should include desktop and narrow-screen checks with synthetic content. Respect reduced-motion and keyboard accessibility.

## Pull requests

Keep changes focused. Never include `.env`, real media, databases, keys, tokens, local NAS addresses or private diagnostics. Add documentation for behavior/configuration changes and update the changelog. Contributions are licensed under the repository's MIT license; preserve third-party attribution.

Be respectful, specific and constructive in discussions. Report security issues privately as described in [SECURITY.md](SECURITY.md).

## License of contributions

SuperGallery is licensed under Apache-2.0 by Sai Krishna Daddala. Contributions you submit are accepted under the same license (Apache-2.0, section 5). Keep the `LICENSE` and `NOTICE` files and existing copyright notices intact.
