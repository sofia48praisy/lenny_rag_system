from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings

engine = create_async_engine(settings().database_url, pool_pre_ping=True, pool_size=10)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Episode(Base):
    __tablename__ = 'episodes'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    guest: Mapped[str] = mapped_column(Text)
    published: Mapped[date | None]
    url: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(Text)


class Chunk(Base):
    __tablename__ = 'chunks'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    episode_id: Mapped[str] = mapped_column(ForeignKey('episodes.id', ondelete='CASCADE'))
    ordinal: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(String(32))
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    __table_args__ = (
        UniqueConstraint('episode_id', 'ordinal'),
        Index('ix_chunks_embedding_hnsw', 'embedding', postgresql_using='hnsw',
              postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )


class Session(Base):
    __tablename__ = 'sessions'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(160), default='New research')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey('sessions.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Artifact(Base):
    __tablename__ = 'artifacts'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(ForeignKey('messages.id', ondelete='CASCADE'), unique=True)
    artifact_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)


async def initialize():
    async with engine.begin() as connection:
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        await connection.run_sync(Base.metadata.create_all)
