from typing import List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.domain.models import ShiftSlot, RosterSolution, OptimizationRequest
from app.application.services.optimizer_service import RosterOptimizerService
from app.infrastructure.repositories.doctor_repository import DoctorRepository
from app.api.deps import get_doctor_repo

router = APIRouter()

# DTO (Data Transfer Object) específico para a requisição da API
# Não precisamos enviar a lista de médicos aqui, pois pegamos do banco
class RosterGenerationRequest(BaseModel):
    period_start: date
    period_end: date
    slots_to_fill: List[ShiftSlot] # O frontend define quais plantões precisam ser cobertos
    weight_cost: float = 1.0
    weight_preference: float = 2.0

@router.post("/optimize", response_model=List[RosterSolution])
async def generate_roster(
    request_data: RosterGenerationRequest,
    doctor_repo: DoctorRepository = Depends(get_doctor_repo)
):
    """
    Gera a escala otimizada baseada nos médicos cadastrados no banco
    e nos Slots enviados na requisição.
    """
    
    # 1. Buscar médicos disponíveis no banco de dados
    # (Em um sistema real, filtraríamos apenas médicos ativos/válidos)
    active_doctors = await doctor_repo.get_all_active_doctors()

    if not active_doctors:
        raise HTTPException(
            status_code=400, 
            detail="Não há médicos cadastrados para gerar a escala."
        )

    # 2. Montar o Objeto de Domínio para o Motor de Otimização
    optimization_request = OptimizationRequest(
        period_start=request_data.period_start,
        period_end=request_data.period_end,
        doctors=active_doctors, # Injetamos os médicos do banco aqui
        slots_to_fill=request_data.slots_to_fill,
        weight_cost=request_data.weight_cost,
        weight_preference=request_data.weight_preference
    )

    # 3. Executar o Serviço de Otimização
    optimizer_service = RosterOptimizerService()
    
    try:
        # O cálculo é CPU-bound. Em alta escala, usaríamos Celery/BackgroundTasks.
        # Para este MVP, rodamos direto (o solver é rápido para instâncias médias).
        solutions = optimizer_service.solve(optimization_request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no motor de otimização: {str(e)}")

    if not solutions:
        raise HTTPException(
            status_code=422, # Unprocessable Entity
            detail="Inviável (Infeasible). Não foi possível encontrar uma solução que respeite todas as regras rígidas. Tente adicionar mais médicos ou remover restrições."
        )

    # 4. (Opcional) Salvar a solução no banco de dados aqui
    # await roster_repo.save_solution(solutions)

    return solutions