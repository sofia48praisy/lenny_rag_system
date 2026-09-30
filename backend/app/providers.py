import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import anthropic
import httpx

from app.config import Settings, settings


class LLMProviderInterface(ABC):
    @abstractmethod
    def stream(self, system: str, question: str) -> AsyncIterator[str]:
        raise NotImplementedError

    async def complete(self, system: str, question: str) -> str:
        return ''.join([token async for token in self.stream(system, question)])


class OllamaProvider(LLMProviderInterface):
    def __init__(self, config: Settings):
        self.config = config

    async def stream(self, system, question):
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.config.model_timeout, connect=10)) as client:
            async with client.stream('POST', f'{self.config.ollama_base_url}/api/chat', json={
                'model': self.config.ollama_model,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': question}],
                'stream': True,
                'options': {'temperature': 0.2, 'num_ctx': self.config.ollama_context,
                            'num_predict': self.config.ollama_max_tokens},
            }) as response:
                response.raise_for_status()
                finished = False
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get('error'):
                        raise RuntimeError('Ollama generation failed')
                    if event.get('message', {}).get('content'):
                        yield event['message']['content']
                    if event.get('done'):
                        if event.get('done_reason') == 'length':
                            raise RuntimeError('Generation exceeded the token budget')
                        finished = True
                if not finished:
                    raise RuntimeError('Ollama stream ended unexpectedly')


class AnthropicProvider(LLMProviderInterface):
    def __init__(self, config: Settings):
        self.config = config

    async def stream(self, system, question):
        async with anthropic.AsyncAnthropic(api_key=self.config.anthropic_api_key, timeout=180, max_retries=2) as client:
            async with client.messages.stream(
                model=self.config.anthropic_model, max_tokens=2800, temperature=0.2,
                system=system, messages=[{'role': 'user', 'content': question}],
            ) as stream:
                async for token in stream.text_stream:
                    yield token
                final = await stream.get_final_message()
                if final.stop_reason != 'end_turn':
                    raise RuntimeError('Cloud generation did not finish normally')


def get_provider(name: str | None = None, config: Settings | None = None) -> LLMProviderInterface:
    config = config or settings()
    name = name or config.default_llm_provider
    if name == 'ollama':
        return OllamaProvider(config)
    if name == 'anthropic':
        if not config.anthropic_api_key:
            raise ValueError('Anthropic is not configured. Set ANTHROPIC_API_KEY or select Ollama.')
        return AnthropicProvider(config)
    raise ValueError('Unknown provider. Choose ollama or anthropic.')


async def embed(texts: list[str], *, query=False) -> list[list[float]]:
    config = settings()
    prefix = 'search_query: ' if query else 'search_document: '
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=10)) as client:
        for attempt in range(3):
            try:
                response = await client.post(f'{config.ollama_base_url}/api/embed', json={
                    'model': config.embedding_model, 'input': [prefix + t for t in texts], 'truncate': False,
                })
                response.raise_for_status()
                vectors = response.json()['embeddings']
                if len(vectors) != len(texts) or any(len(v) != 768 for v in vectors):
                    raise ValueError('Expected 768-dimensional nomic embeddings; rebuild schema for other models.')
                return vectors
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code not in (429, 502, 503, 504):
                    raise
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError('Embedding retries exhausted')
