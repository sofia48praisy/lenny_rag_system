"""Opt in: TEST_DATABASE_URL=postgresql+asyncpg://... pytest -m integration.
Uses a temporary table and rolls back; does not alter application data.
"""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.integration
async def test_real_pgvector_cosine_ranking():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL not set; PostgreSQL integration not available')
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            async with conn.begin():
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                await conn.execute(text('CREATE TEMP TABLE test_vectors (name text, embedding vector(3)) ON COMMIT DROP'))
                await conn.execute(text("INSERT INTO test_vectors VALUES ('relevant', '[1,0,0]'), ('unrelated', '[0,1,0]')"))
                await conn.execute(text('CREATE INDEX ON test_vectors USING hnsw (embedding vector_cosine_ops)'))
                rows = (await conn.execute(text("SELECT name, 1 - (embedding <=> '[1,0,0]'::vector) AS score FROM test_vectors ORDER BY embedding <=> '[1,0,0]'::vector"))).all()
                assert rows[0].name == 'relevant' and rows[0].score == pytest.approx(1)
                assert rows[1].score == pytest.approx(0)
    finally:
        await engine.dispose()
