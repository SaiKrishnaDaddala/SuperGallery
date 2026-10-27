import json
import sqlite3
from app.upgrade import backup


def test_consistent_wal_backup_is_created_once(tmp_path):
    with sqlite3.connect(tmp_path/'index.db') as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('CREATE TABLE sample(value)')
        c.execute('INSERT INTO sample VALUES (42)')
        c.commit()
        (tmp_path/'secret.key').write_text('fixture-key')
        backup(tmp_path)
        target=tmp_path/'backups/before-2.2'
        with sqlite3.connect(target/'index.db') as b:
            assert b.execute('SELECT value FROM sample').fetchone()[0]==42
        assert (target/'secret.key').read_text()=='fixture-key'
        stamp=json.loads((target/'complete.json').read_text())['created']
        c.execute('UPDATE sample SET value=43');c.commit()
        backup(tmp_path)
        assert json.loads((target/'complete.json').read_text())['created']==stamp
