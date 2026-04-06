from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from resulve.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_sessionmaker = None


def get_engine():
    global _engine, _sessionmaker
    if _engine is None:
        s = get_settings()
        _engine = create_async_engine(s.database_url, pool_size=10, max_overflow=20)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_sessionmaker():
    if _sessionmaker is None:
        get_engine()
    return _sessionmaker


@asynccontextmanager
async def session_scope():
    sm = get_sessionmaker()
    async with sm() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


async def get_session():
    sm = get_sessionmaker()
    async with sm() as s:
        yield s
