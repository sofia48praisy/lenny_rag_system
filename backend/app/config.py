from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'postgresql+asyncpg://lenny:lenny_local_dev@localhost:5432/lenny'
    ollama_base_url: str = 'http://localhost:11434'
    ollama_model: str = 'llama3.2:3b'
    ollama_context: int = Field(default=8192, ge=4096, le=32768)
    ollama_max_tokens: int = Field(default=2800, ge=128, le=4096)
    model_timeout: float = Field(default=600, ge=30, le=1800)
    embedding_model: str = 'nomic-embed-text'
    default_llm_provider: Literal['ollama', 'anthropic'] = 'ollama'
    anthropic_api_key: str = ''
    anthropic_model: str = 'claude-sonnet-4-6'
    retrieval_threshold: float = Field(default=0.55, ge=0, le=1)
    top_k: int = Field(default=5, ge=1, le=10)
    cors_origins: str = 'http://localhost:5173,http://localhost:3000'


@lru_cache
def settings() -> Settings:
    return Settings()
