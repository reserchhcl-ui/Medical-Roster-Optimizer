from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.api import api_router
from app.infrastructure.database import create_tables, engine

# Lifespan events (Novo padrão do FastAPI para inicialização/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Garantir que tabelas existam
    # Em produção, usaríamos Alembic para migrações, não create_tables direto
    print("🚀 Sistema iniciando... Verificando banco de dados.")
    async with engine.begin() as conn:
        from app.infrastructure.orm_models import Base # Importa para registrar metadata
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Shutdown
    print("🛑 Sistema desligando...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {"status": "active", "system": "medical-roster"}