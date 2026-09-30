"""Run from backend: python -m scripts.ingest ../data/raw/lenny/podcasts"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from sqlalchemy import delete, text

from app.config import settings
from app.db import Chunk, Episode, SessionFactory, engine, initialize
from app.providers import embed
from app.rag import chunk_episode, parse_episode


async def ingest(root: Path):
    files = sorted(p for p in root.rglob('*') if p.suffix.lower() in ('.md', '.txt') and p.name.lower() not in ('readme.md', 'license.md'))
    if not files:
        raise ValueError(f'No transcripts found in {root}')
    await initialize()
    manifest_path = root.parent / 'manifest.json'
    provenance = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        provenance = {entry['path']: entry['url'] for entry in manifest.get('files', [])}
    # Keep a dedicated connection for a session-level lock across per-episode commits.
    async with engine.connect() as lock:
        acquired = await lock.scalar(text('SELECT pg_try_advisory_lock(714203)'))
        if not acquired:
            raise RuntimeError('Another ingestion is already running')
        try:
            for path in files:
                relative = path.relative_to(root).as_posix()
                episode_id = hashlib.sha256(relative.encode()).hexdigest()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                async with SessionFactory() as db:
                    old = await db.get(Episode, episode_id)
                    if old and old.content_hash == digest and old.embedding_model == settings().embedding_model:
                        print(json.dumps({'event': 'skip', 'file': relative}), flush=True)
                        continue
                    episode = parse_episode(path)
                    chunks = chunk_episode(episode)
                    if not chunks:
                        raise ValueError(f'Empty transcript: {relative}')
                    vectors = []
                    for offset in range(0, len(chunks), 8):
                        vectors.extend(await embed([c['content'] for c in chunks[offset:offset + 8]]))
                    if old:
                        await db.delete(old)
                        await db.flush()
                    db.add(Episode(id=episode_id, title=episode.title, guest=episode.guest,
                                   published=episode.published,
                                   url=episode.url or provenance.get(f'{root.name}/{relative}', ''), source_path=relative,
                                   content_hash=digest, embedding_model=settings().embedding_model))
                    await db.flush()
                    for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                        db.add(Chunk(episode_id=episode_id, ordinal=ordinal, embedding=vector, **chunk))
                    await db.commit()
                    print(json.dumps({'event': 'ingested', 'file': relative, 'chunks': len(chunks)}), flush=True)
        finally:
            await lock.execute(text('SELECT pg_advisory_unlock(714203)'))
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    asyncio.run(ingest(parser.parse_args().path))
