from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app import main
from app.rag import REFUSAL


class FakeDB:
    def __init__(self):
        self.session = SimpleNamespace(id=uuid4(), title='New research', updated_at=datetime.now(timezone.utc))
        self.objects = []
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def get(self, *args): return self.session
    async def scalar(self, *args): return True
    def add(self, obj):
        obj.id = uuid4()
        if hasattr(obj, 'created_at'): obj.created_at = datetime.now(timezone.utc)
        self.objects.append(obj)
    async def flush(self): pass
    async def commit(self): self.committed = True
    async def rollback(self): self.rolled_back = True


@pytest.fixture
def db(monkeypatch):
    value = FakeDB()
    monkeypatch.setattr(main, 'SessionFactory', lambda: value)
    return value


async def post_chat(db, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
        return await client.post('/api/chat', json={'session_id': str(db.session.id), 'question': 'How do we grow?', **kwargs})


async def test_no_evidence_refuses_without_generation(monkeypatch, db):
    provider = SimpleNamespace(stream=lambda *args: pytest.fail('LLM must not run'))
    monkeypatch.setattr(main, 'get_provider', lambda *args: provider)
    monkeypatch.setattr(main, 'retrieve', AsyncMock(return_value=[]))
    response = await post_chat(db)
    assert response.status_code == 200
    assert REFUSAL in response.text and 'event: done' in response.text
    assert db.committed and len(db.objects) == 2


async def test_success_stream_persists_artifact(monkeypatch, db):
    source = {'label': '[Episode: Ada, 00:01:22]'}
    class Provider:
        async def stream(self, *args):
            yield '# Growth\n'
            yield 'Test activation. [Episode: Ada, 00:01:22]'
    monkeypatch.setattr(main, 'get_provider', lambda *args: Provider())
    monkeypatch.setattr(main, 'retrieve', AsyncMock(return_value=[source]))
    response = await post_chat(db, mode='essay')
    assert 'event: token' in response.text and 'event: message' in response.text
    assert len(db.objects) == 3 and db.committed


async def test_stream_failure_rolls_back(monkeypatch, db):
    class Provider:
        async def stream(self, *args):
            yield 'partial'
            raise RuntimeError('secret-provider-details')
    monkeypatch.setattr(main, 'get_provider', lambda *args: Provider())
    monkeypatch.setattr(main, 'retrieve', AsyncMock(return_value=[{'label': '[Episode: Ada, Topic]'}]))
    response = await post_chat(db)
    assert 'event: error' in response.text
    assert 'secret-provider-details' not in response.text
    assert db.rolled_back and not db.committed


async def test_missing_citation_is_replaced(monkeypatch, db):
    class Provider:
        async def stream(self, *args): yield 'An unsupported answer'
    monkeypatch.setattr(main, 'get_provider', lambda *args: Provider())
    monkeypatch.setattr(main, 'retrieve', AsyncMock(return_value=[{'label': '[Episode: Ada, Topic]'}]))
    await post_chat(db)
    assert db.objects[-1].content == REFUSAL


async def test_provider_header_overrides_body(monkeypatch, db):
    chosen = []
    monkeypatch.setattr(main, 'get_provider', lambda name: chosen.append(name))
    monkeypatch.setattr(main, 'retrieve', AsyncMock(return_value=[]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
        await client.post('/api/chat', headers={'X-LLM-Provider': 'anthropic'},
                          json={'session_id': str(db.session.id), 'question': 'Activation', 'provider': 'ollama'})
    assert chosen == ['anthropic']
