import json

import httpx
import pytest

from app import providers
from app.config import Settings


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


async def test_ollama_stream_protocol(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body['stream'] is True and body['model'] == 'llama3.2:3b'
        return httpx.Response(200, text='{"message":{"content":"Hello"},"done":false}\n{"message":{"content":" world"},"done":true,"done_reason":"stop"}\n')
    mock_http(monkeypatch, handler)
    provider = providers.OllamaProvider(Settings(_env_file=None))
    assert await provider.complete('Use evidence', 'Question') == 'Hello world'


async def test_truncated_model_stream_fails(monkeypatch):
    mock_http(monkeypatch, lambda request: httpx.Response(200, text='{"message":{"content":"partial"}}\n'))
    provider = providers.OllamaProvider(Settings(_env_file=None))
    with pytest.raises(RuntimeError, match='unexpectedly'):
        await provider.complete('Use evidence', 'Question')


async def test_embeddings_use_prefix_and_validate_dimensions(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body['input'] == ['search_query: retention']
        assert body['truncate'] is False
        return httpx.Response(200, json={'embeddings': [[1.0] * 768]})
    mock_http(monkeypatch, handler)
    assert len((await providers.embed(['retention'], query=True))[0]) == 768


async def test_wrong_embedding_dimensions_fail(monkeypatch):
    mock_http(monkeypatch, lambda request: httpx.Response(200, json={'embeddings': [[1.0] * 384]}))
    with pytest.raises(ValueError, match='768'):
        await providers.embed(['retention'])
