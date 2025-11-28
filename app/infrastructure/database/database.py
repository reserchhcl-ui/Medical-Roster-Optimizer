from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Em um cenário real, a URL viria do .env (settings.DATABASE_URL)
# Exemplo Postgres: "postgresql+asyncpg://user:pass@localhost/medical_db"
# Para este brainstorm, usaremos SQLite Async para facilitar sua execução local sem docker
DATABASE_URL = "sqlite+aiosqlite:///./medical_roster.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False, # Mude para True para ver as queries SQL no log (debug)
    future=True
)

# Factory de sessões assíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM do SQLAlchemy"""
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency Injection para FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Função auxiliar para criar as tabelas (apenas para dev/teste)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)