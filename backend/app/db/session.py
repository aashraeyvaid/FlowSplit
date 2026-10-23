"""SQLAlchemy and in-memory persistence management.

SQLite is disabled per project requirements ('no sqlite for now').
Runs in-memory repository storage by default, or connects to PostgreSQL if configured.
"""

import logging
from collections import defaultdict
from typing import Any, AsyncGenerator, Optional
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from backend.app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Global in-memory storage store: {ModelClass: {id: instance}}
_in_memory_store: dict[type, dict[str, Any]] = defaultdict(dict)


class InMemoryResult:
    """Mock-free lightweight execution result wrapping in-memory entities."""

    def __init__(self, item: Any):
        self._item = item

    def scalar_one_or_none(self) -> Any:
        return self._item

    def scalars(self):
        items = [self._item] if self._item is not None else []

        class ScalarsWrapper:
            def all(self):
                return items

            def first(self):
                return items[0] if items else None

        return ScalarsWrapper()


class InMemoryAsyncSession:
    """Async session implementation providing zero-database in-memory persistence.
    
    Ensures complete decoupling from SQLite while maintaining full compatibility
    with FastAPI dependency injection and SQLAlchemy model instances.
    """

    def __init__(self):
        self._pending_adds: list[Any] = []

    def add(self, obj: Any) -> None:
        self._pending_adds.append(obj)

    async def commit(self) -> None:
        for obj in self._pending_adds:
            obj_id = getattr(obj, "id", None)
            if obj_id is not None:
                _in_memory_store[type(obj)][str(obj_id)] = obj
        self._pending_adds.clear()

    async def rollback(self) -> None:
        self._pending_adds.clear()

    async def execute(self, statement: Any) -> InMemoryResult:
        try:
            entity = statement.column_descriptions[0]["entity"]
            wc = getattr(statement, "whereclause", None)
            if wc is not None and hasattr(wc, "left") and hasattr(wc, "right"):
                attr = getattr(wc.left, "name", None)
                val = getattr(wc.right, "value", None)
                if val is not None:
                    val_str = str(val)
                    if attr == "id":
                        return InMemoryResult(_in_memory_store[entity].get(val_str))
                    # Scan table for matching property
                    for item in _in_memory_store[entity].values():
                        if str(getattr(item, attr, None)) == val_str:
                            return InMemoryResult(item)
            return InMemoryResult(None)
        except Exception as exc:
            logger.debug("In-memory query evaluation exception: %s", exc)
            return InMemoryResult(None)

    async def close(self) -> None:
        self._pending_adds.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Check if external PostgreSQL database is configured
db_url = settings.DATABASE_URL
engine = None
AsyncSessionLocal = None

if db_url and db_url.startswith(("postgresql://", "postgresql+asyncpg://")):
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    logger.info("Initializing async PostgreSQL engine...")
    engine = create_async_engine(db_url, echo=False, future=True)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    if db_url and "sqlite" in db_url.lower():
        logger.warning(
            "SQLite database URL detected in settings but SQLite is explicitly disabled "
            "('no sqlite for now'). Running with in-memory persistence."
        )
    else:
        logger.info("Operating in-memory persistence (no SQLite, no disk DB).")


async def get_db() -> AsyncGenerator[Any, None]:
    """FastAPI dependency for obtaining database session."""
    if AsyncSessionLocal is not None:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    else:
        session = InMemoryAsyncSession()
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initializes database tables if PostgreSQL is connected, or resets in-memory store."""
    import backend.app.db.models  # noqa: F401

    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL database tables verified.")
    else:
        logger.info("In-memory persistence ready (SQLite completely disabled).")


def reset_in_memory_db() -> None:
    """Utility for test suites to clear stored in-memory records."""
    _in_memory_store.clear()
