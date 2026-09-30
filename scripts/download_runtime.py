"""Download portable local runtime tools to a user-selected disk; no services installed.

Run explicitly with --destination. GitHub assets are verified against published SHA-256.
Database archives come directly from the database vendor over HTTPS; their hashes are recorded.
"""
import argparse
import hashlib
import json
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

ASSETS = [
    ('postgres-community', 'https://get.enterprisedb.com/postgresql/postgresql-16.15-4-windows-x64-binaries.zip', None),
    # Community-maintained MSVC build compatible with the EDB Windows distribution.
    ('pgvector-msvc', 'https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/0.8.6_16/vector.v0.8.6-pg16.zip', 'faeaecb100488397ce5d38424b8c931be0f29e1668be7d4e75c26fe2eb056522'),
    ('ollama', 'https://github.com/ollama/ollama/releases/download/v0.35.0/ollama-windows-amd64.zip', 'd6f7d3dd4f5d013553a78c1e78b2521fcf41d43dd2863e4596cdc046fe6036db'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--only', choices=[a[0] for a in ASSETS])
    args = parser.parse_args()
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / 'download-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else []
    for name, url, expected in ASSETS:
        if args.only and args.only != name:
            continue
        archive = root / (name + '.zip')
        if not archive.exists():
            if shutil.disk_usage(root).free < 5 * 1024**3:
                raise RuntimeError('Need at least 5 GB free before downloading runtime archives')
            request = urllib.request.Request(url, headers={'User-Agent': 'LennyGrowthSetup'})
            partial = archive.with_suffix('.partial')
            with urllib.request.urlopen(request, timeout=120) as response, partial.open('wb') as output:
                total = int(response.headers.get('Content-Length', 0))
                received = 0
                reported = time.monotonic()
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    received += len(chunk)
                    if time.monotonic() - reported > 10:
                        print(f'{name}: {received // 1048576}/{total // 1048576} MB downloaded', flush=True)
                        reported = time.monotonic()
            partial.replace(archive)
        with archive.open('rb') as file:
            digest = hashlib.file_digest(file, 'sha256').hexdigest()
        if expected and digest != expected:
            raise RuntimeError(f'Checksum mismatch: {name}')
        target = root / name
        target.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as zipped:
            for entry in zipped.infolist():
                resolved = (target / entry.filename).resolve()
                if not resolved.is_relative_to(target):
                    raise RuntimeError('Unsafe archive member')
            zipped.extractall(target)
        manifest = [entry for entry in manifest if entry['name'] != name]
        manifest.append({'name': name, 'url': url, 'sha256': digest, 'published_checksum_verified': bool(expected)})
        print(f'{name}: extracted to {target}', flush=True)
    (root / 'download-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
