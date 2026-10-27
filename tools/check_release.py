"""Check tracked source for accidental runtime data and common credential formats."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b',
    rb'\bgithub_pat_[A-Za-z0-9_]{30,}\b',
    rb'\bAKIA[0-9A-Z]{16}\b',
]
FORBIDDEN_PARTS = {'.work', '.test-config', 'config', 'data', 'library', 'sample-library', '__pycache__', '.venv', 'venv'}
FORBIDDEN_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.key', '.pem', '.pfx', '.onnx', '.pyc', '.log'}


def tracked():
    return subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')[:-1]


def main():
    errors = []
    files = tracked()
    if not files:
        raise SystemExit('No tracked files; stage the intended source first.')
    for name in files:
        path = ROOT / name
        if path.is_symlink() or any(part in FORBIDDEN_PARTS for part in path.relative_to(ROOT).parts) or path.suffix.lower() in FORBIDDEN_SUFFIXES or (path.name.startswith('.env') and path.name != '.env.example'):
            errors.append(name + ': forbidden release file')
            continue
        content = path.read_bytes()
        if any(re.search(pattern, content) for pattern in PATTERNS):
            errors.append(name + ': possible credential (value withheld)')
    for required in ('README.md', 'LICENSE', 'NOTICE', 'SECURITY.md', 'compose.yaml', '.env.example', 'docs/INSTALL.md', 'docs/UPGRADING.md'):
        if required not in files:
            errors.append('Missing required release file: ' + required)
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'Release file checks passed: {len(files)} tracked files. This is a guardrail, not a complete secret audit.')


if __name__ == '__main__':
    main()
