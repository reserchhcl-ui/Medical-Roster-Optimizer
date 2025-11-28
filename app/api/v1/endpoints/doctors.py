from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.domain.models import Doctor
from app.infrastructure.repositories.doctor_repository import DoctorRepository
from app.api.deps import get_doctor_repo

router = APIRouter()

@router.post("/", response_model=Doctor, status_code=status.HTTP_201_CREATED)
async def create_doctor(
    doctor_in: Doctor,
    repo: DoctorRepository = Depends(get_doctor_repo)
):
    """
    Cadastra um novo médico e suas restrições/preferências.
    O Payload deve seguir estritamente o modelo de domínio.
    """
    # Verificação simples de duplicidade (em prod seria melhor tratar exceção do banco)
    existing_doctors = await repo.get_all()
    if any(d.crm == doctor_in.crm for d in existing_doctors):
        raise HTTPException(
            status_code=400, 
            detail=f"Médico com CRM {doctor_in.crm} já existe."
        )

    try:
        # A conversão Domain -> ORM acontece dentro do repo
        await repo.create_from_domain(doctor_in)
        return doctor_in
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[Doctor])
async def list_doctors(
    skip: int = 0,
    limit: int = 100,
    repo: DoctorRepository = Depends(get_doctor_repo)
):
    """
    Lista todos os médicos ativos no sistema.
    Usado pelo Frontend para mostrar quem está disponível para a escala.
    """
    doctors = await repo.get_all_active_doctors()
    return doctors[skip : skip + limit]