"""Take a consistent, private restore point before the 2.2 index migration."""
import json
import os
import shutil
import sqlite3
import time
from contextlib import closing
from pathlib import Path


def backup(directory, version='2.2'):
    directory = Path(directory)
    destination = directory / "backups" / ('before-'+version)
    if (destination / "complete.json").exists() or not (directory / "index.db").exists():
        return
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.parent.chmod(0o700)
    destination.chmod(0o700)
    files = []
    for name in ("index.db", "security.sqlite3"):
        source = directory / name
        if not source.exists():
            continue
        temporary = destination / (name + ".partial")
        # SQLite backup includes committed WAL data without copying live database files.
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("Could not verify the pre-upgrade database backup")
        temporary.chmod(0o600)
        os.replace(temporary, destination / name)
        files.append(name)
    for name in ("password.json", "secret.key"):
        source = directory / name
        if source.exists():
            shutil.copyfile(source, destination / name)
            (destination / name).chmod(0o600)
            files.append(name)
    marker = destination / "complete.json"
    marker.write_text(json.dumps({"created": time.time(), "files": files}, indent=2))
    marker.chmod(0o600)
