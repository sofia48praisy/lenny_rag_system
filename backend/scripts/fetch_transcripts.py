"""Download only public podcast Markdown, with immutable revision provenance."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

REPO = 'LennysNewsletter/lennys-newsletterpodcastdata'


def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'LennyGrowthAssistant/1.0'}), timeout=60) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('data/raw/lenny'))
    parser.add_argument('--limit', type=int, default=0, help='0 downloads all public podcast files')
    parser.add_argument('--refresh', action='store_true', help='Download a new revision instead of using a verified local snapshot')
    args = parser.parse_args()
    manifest_path = args.output / 'manifest.json'
    if manifest_path.exists() and not args.refresh:
        saved = json.loads(manifest_path.read_text(encoding='utf-8'))
        entries = saved.get('files', [])
        if entries and all((args.output / entry['path']).is_file() and
                           hashlib.sha256((args.output / entry['path']).read_bytes()).hexdigest() == entry['sha256']
                           for entry in entries):
            print(f'Using verified local snapshot: {len(entries)} transcripts, revision {saved["revision"]}')
            return
    revision = json.loads(fetch(f'https://api.github.com/repos/{REPO}/commits/main'))['sha']
    tree = json.loads(fetch(f'https://api.github.com/repos/{REPO}/git/trees/{revision}?recursive=1'))
    files = [x['path'] for x in tree['tree'] if x['path'].startswith('podcasts/') and x['path'].endswith('.md')]
    if args.limit:
        files = files[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'repository': f'https://github.com/{REPO}', 'revision': revision, 'files': []}
    for path in files:
        url = f'https://raw.githubusercontent.com/{REPO}/{revision}/{path}'
        content = fetch(url)
        target = args.output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest['files'].append({'path': path, 'url': url, 'sha256': hashlib.sha256(content).hexdigest()})
        print(f'Downloaded {path}', flush=True)
    for name in ['README.md', 'LICENSE.md']:
        (args.output / name).write_bytes(fetch(f'https://raw.githubusercontent.com/{REPO}/{revision}/{name}'))
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Saved {len(files)} transcripts at revision {revision}')


if __name__ == '__main__':
    main()
