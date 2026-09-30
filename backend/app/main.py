import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text

from app.config import settings
from app.db import Artifact, Chunk, Episode, Message, Session, SessionFactory, engine, initialize, now
from app.providers import get_provider
from app.rag import REFUSAL, build_prompt, extract_artifact, retrieve, validate_citations

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('lenny')


@asynccontextmanager
async def lifespan(app):
    for attempt in range(6):
        try:
            await initialize()
            break
        except Exception as error:
            logger.warning(json.dumps({'event': 'database_startup_retry', 'attempt': attempt + 1, 'type': type(error).__name__}))
            if attempt == 5:
                raise
            await asyncio.sleep(min(2 ** attempt, 10))
    yield
    await engine.dispose()


app = FastAPI(title='Lenny Growth Assistant', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins.split(','),
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'X-LLM-Provider'])


@app.middleware('http')
async def request_logging(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    logger.info(json.dumps({'event': 'request', 'id': request_id, 'method': request.method,
                           'path': request.url.path, 'status': response.status_code,
                           'elapsed_ms': round((time.perf_counter() - start) * 1000)}))
    return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.error(json.dumps({'event': 'request_error', 'id': request_id, 'type': type(error).__name__}))
    return JSONResponse(status_code=500, content={'detail': 'Request failed. Check service health and retry.', 'request_id': request_id})


class NewSession(BaseModel):
    title: str = Field(default='New research', max_length=160, min_length=1)


class ChatRequest(BaseModel):
    session_id: UUID
    question: str = Field(min_length=1, max_length=4000)
    provider: Literal['ollama', 'anthropic'] | None = None
    mode: Literal['answer', 'essay', 'html'] = 'answer'

    @field_validator('question')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Enter a question')
        return value.strip()


def session_json(session):
    return {'id': str(session.id), 'title': session.title,
            'created_at': session.created_at.isoformat(), 'updated_at': session.updated_at.isoformat()}


def artifact_json(artifact):
    return {'id': str(artifact.id), 'artifact_type': artifact.artifact_type,
            'title': artifact.title, 'content': artifact.content} if artifact else None


def message_json(message, artifact=None):
    return {'id': str(message.id), 'role': message.role, 'content': message.content,
            'sources': message.sources, 'created_at': message.created_at.isoformat(),
            'artifact': artifact_json(artifact)}


@app.post('/api/sessions', status_code=201)
async def create_session(body: NewSession):
    async with SessionFactory() as db:
        session = Session(title=body.title)
        db.add(session)
        await db.commit()
        return session_json(session)


@app.get('/api/sessions')
async def list_sessions():
    async with SessionFactory() as db:
        sessions = (await db.scalars(select(Session).order_by(Session.updated_at.desc()).limit(100))).all()
        return [session_json(s) for s in sessions]


@app.get('/api/sessions/{session_id}')
async def session_history(session_id: UUID):
    async with SessionFactory() as db:
        session = await db.get(Session, session_id)
        if not session:
            raise HTTPException(404, 'Session not found')
        rows = (await db.execute(select(Message, Artifact).outerjoin(Artifact, Artifact.message_id == Message.id)
                                 .where(Message.session_id == session_id).order_by(Message.created_at, Message.id))).all()
        return {**session_json(session), 'messages': [message_json(m, a) for m, a in rows]}


def sse(event, data):
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


@app.post('/api/chat')
async def chat(body: ChatRequest, request: Request, x_llm_provider: str | None = Header(default=None)):
    try:
        provider = get_provider(x_llm_provider or body.provider)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    async with SessionFactory() as db:
        if not await db.get(Session, body.session_id):
            raise HTTPException(404, 'Session not found')

    async def events():
        started = time.perf_counter()
        first_token_ms = None
        async with SessionFactory() as db:
            try:
                # Transaction-scoped lock releases on commit, failure or cancellation.
                locked = await db.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'),
                                         {'key': body.session_id.int % (2**63 - 1)})
                if not locked:
                    yield sse('error', {'detail': 'This session is already generating. Wait and retry.'})
                    return
                sources = await retrieve(db, body.question)
                yield sse('sources', sources)
                content = ''
                if not sources:
                    content = REFUSAL
                    yield sse('token', {'text': content})
                else:
                    async for token in provider.stream(build_prompt(sources, body.mode), body.question):
                        if await request.is_disconnected():
                            return
                        if first_token_ms is None:
                            first_token_ms = round((time.perf_counter() - started) * 1000)
                        content += token
                        if len(content) > 100000:
                            raise ValueError('Response size limit exceeded')
                        yield sse('token', {'text': token})
                    if not validate_citations(content, sources):
                        content = REFUSAL
                artifact_data = extract_artifact(content, body.mode)
                session = await db.get(Session, body.session_id)
                session.updated_at = now()
                if session.title == 'New research':
                    session.title = body.question[:100]
                user_message = Message(session_id=body.session_id, role='user', content=body.question, sources=[])
                db.add(user_message)
                await db.flush()
                assistant = Message(session_id=body.session_id, role='assistant', content=content, sources=sources)
                db.add(assistant)
                await db.flush()
                artifact = Artifact(message_id=assistant.id, **artifact_data) if artifact_data else None
                if artifact:
                    db.add(artifact)
                await db.commit()
                yield sse('message', message_json(assistant, artifact))
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                yield sse('done', {'first_token_ms': first_token_ms, 'elapsed_ms': elapsed_ms})
                logger.info(json.dumps({'event': 'generation_complete', 'provider': type(provider).__name__,
                                       'first_token_ms': first_token_ms, 'elapsed_ms': elapsed_ms,
                                       'sources': len(sources), 'mode': body.mode}))
            except asyncio.CancelledError:
                raise
            except Exception as error:
                await db.rollback()
                logger.error(json.dumps({'event': 'generation_error', 'type': type(error).__name__}))
                yield sse('error', {'detail': 'Generation failed. Check database, model availability and provider configuration, then retry.'})
    return StreamingResponse(events(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no',
    })


@app.get('/api/health')
async def health():
    state = {'database': False, 'vector_index': False, 'chunks': 0, 'episodes': 0,
             'ollama': False, 'embedding_model': False, 'chat_model': False,
             'providers': {'ollama': True, 'anthropic': bool(settings().anthropic_api_key)}}
    try:
        async with SessionFactory() as db:
            await db.execute(text('SELECT 1'))
            state['database'] = True
            state['chunks'] = await db.scalar(select(func.count()).select_from(Chunk).join(Episode).where(Episode.embedding_model == settings().embedding_model))
            state['episodes'] = await db.scalar(select(func.count()).select_from(Episode).where(Episode.embedding_model == settings().embedding_model))
            state['vector_index'] = bool(await db.scalar(text("SELECT to_regclass('ix_chunks_embedding_hnsw') IS NOT NULL")))
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f'{settings().ollama_base_url}/api/tags')
            response.raise_for_status()
            names = {x['name'] for x in response.json()['models']}
            present = lambda model: model in names or model + ':latest' in names
            state.update(ollama=True, embedding_model=present(settings().embedding_model), chat_model=present(settings().ollama_model))
    except Exception:
        pass
    ready = all(state[k] for k in ('database', 'vector_index', 'chunks', 'embedding_model', 'chat_model'))
    return JSONResponse({**state, 'status': 'ready' if ready else 'not_ready'}, status_code=200 if ready else 503)
