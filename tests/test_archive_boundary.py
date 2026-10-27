import asyncio
import io
import json
import zipfile

import pytest

from app import main, scanner


def test_recursive_download_excludes_symlinks_and_private_folders(tmp_path, monkeypatch):
    root=tmp_path/'library';root.mkdir()
    folder=root/'Album';folder.mkdir()
    (folder/'visible.txt').write_text('public fixture')
    excluded=folder/'.supergallery_trash';excluded.mkdir()
    (excluded/'removed.txt').write_text('excluded fixture')
    external=tmp_path/'outside.txt';external.write_text('outside fixture')
    try:
        (folder/'linked.txt').symlink_to(external)
        (folder/'linked-folder').symlink_to(excluded,target_is_directory=True)
    except OSError:
        pytest.skip('This host does not allow test symlinks; Linux CI runs this regression.')
    monkeypatch.setattr(scanner,'SCAN_ROOTS',[root.as_posix()])
    response=main.zip_download(json.dumps([folder.as_posix()]))
    async def collect():
        return b''.join([chunk async for chunk in response.body_iterator])
    with zipfile.ZipFile(io.BytesIO(asyncio.run(collect()))) as archive:
        assert archive.namelist()==['Album/visible.txt']
        assert archive.read('Album/visible.txt')==b'public fixture'
