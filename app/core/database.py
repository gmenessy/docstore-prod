"""
Asynchrone Datenbank-Session-Verwaltung (SQLAlchemy async).
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.models.database import Base

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Datenbank-Tabellen erstellen."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency fuer FastAPI-Routen."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_store_or_404(db: AsyncSession, store_id: str, load_docs: bool = False, load_entities: bool = False):
    """
    Store laden oder 404 werfen.
    Reduziert Duplikation in allen API-Routern (vorher 10x wiederholt).
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.database import Store, Document

    query = select(Store).where(Store.id == store_id)
    if load_docs and load_entities:
        query = query.options(selectinload(Store.documents).selectinload(Document.entities))
    elif load_docs:
        query = query.options(selectinload(Store.documents))

    result = await db.execute(query)
    store = result.scalar_one_or_none()
    if not store:
        from fastapi import HTTPException
        raise HTTPException(404, f"Sammlung {store_id} nicht gefunden")
    return store
