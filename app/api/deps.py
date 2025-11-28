from typing import AsyncGenerator, Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database import get_db
from app.infrastructure.repositories.doctor_repository import DoctorRepository

# Type Hint para injeção do banco de dados
DBDep = Annotated[AsyncSession, Depends(get_db)]

async def get_doctor_repo(db: DBDep) -> DoctorRepository:
    """
    Injeta o Repositório de Médicos já com a sessão do banco ativa.
    Isso abstrai a persistência dos controllers.
    """
    return DoctorRepository(db)