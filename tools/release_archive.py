"""Create a source-only release archive from committed Git objects."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    args=parser.parse_args()
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[a-z0-9.]+)?',args.tag):
        raise SystemExit('Expected a semantic version tag, such as v2.4.0')
    root=Path(__file__).resolve().parents[1]
    version=re.search(r"VERSION = '([^']+)'",(root/'app/features.py').read_text()).group(1)
    if args.tag!='v'+version:
        raise SystemExit('Tag does not match the application version')
    output=root/'dist';output.mkdir(exist_ok=True)
    archive=output/f'SuperGallery-{args.tag}-source.zip'
    subprocess.run(['git','archive','--format=zip',f'--prefix=SuperGallery-{args.tag}/',f'--output={archive}',args.tag],cwd=root,check=True)
    with archive.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
    (output/'SHA256SUMS').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print(archive.name,digest)


if __name__=='__main__':main()
