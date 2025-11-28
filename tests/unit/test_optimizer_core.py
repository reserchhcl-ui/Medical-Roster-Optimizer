import pytest
from datetime import date, timedelta
from app.domain.models import (
    Doctor, DoctorAttributes, DoctorAvailability, 
    ShiftSlot, SpecialtyEnum, ShiftTypeEnum, OptimizationRequest
)
from app.application.services.optimizer_service import RosterOptimizerService

# --- Fixtures (Dados de Teste Reutilizáveis) ---

@pytest.fixture
def basic_doctors():
    return [
        Doctor(
            id="doc_1", name="Dr. House", crm="111",
            specialties=[SpecialtyEnum.CLINICA_GERAL],
            attributes=DoctorAttributes(seniority_level=5, cost_per_hour=100.0, is_preceptor=False),
            availability=DoctorAvailability(unavailable_dates=[], max_shifts_per_month=10)
        ),
        Doctor(
            id="doc_2", name="Dr. Wilson", crm="222",
            specialties=[SpecialtyEnum.ONCOLOGIA, SpecialtyEnum.CLINICA_GERAL],
            attributes=DoctorAttributes(seniority_level=4, cost_per_hour=100.0, is_preceptor=False),
            availability=DoctorAvailability(unavailable_dates=[], max_shifts_per_month=10)
        )
    ]

@pytest.fixture
def single_slot():
    return ShiftSlot(
        id="slot_1", date=date(2023, 10, 1), 
        shift_type=ShiftTypeEnum.DIURNO,
        required_specialties=[SpecialtyEnum.CLINICA_GERAL],
        required_count=1, sector_id="UTI"
    )

# --- Test Cases ---

def test_basic_allocation_success(basic_doctors, single_slot):
    """Teste: Deve alocar 1 médico quando há disponibilidade e competência."""
    request = OptimizationRequest(
        period_start=date(2023, 10, 1),
        period_end=date(2023, 10, 1),
        doctors=basic_doctors,
        slots_to_fill=[single_slot]
    )
    
    service = RosterOptimizerService()
    result = service.solve(request)
    
    assert len(result) == 1
    assert result[0].slot_id == "slot_1"
    assert result[0].doctor_id in ["doc_1", "doc_2"]

def test_specialty_mismatch():
    """Teste: Não deve alocar médico se ele não tiver a especialidade exigida."""
    cardiologist = Doctor(
        id="doc_cardio", name="Dr. Cardio", crm="333",
        specialties=[SpecialtyEnum.CARDIOLOGIA], # Não é Clinico Geral
        attributes=DoctorAttributes(seniority_level=5, cost_per_hour=200, is_preceptor=False),
        availability=DoctorAvailability()
    )
    
    slot_needs_gp = ShiftSlot(
        id="slot_gp", date=date(2023, 10, 1), shift_type=ShiftTypeEnum.DIURNO,
        required_specialties=[SpecialtyEnum.CLINICA_GERAL], required_count=1, sector_id="ER"
    )

    request = OptimizationRequest(
        period_start=date(2023, 10, 1), period_end=date(2023, 10, 1),
        doctors=[cardiologist], slots_to_fill=[slot_needs_gp]
    )
    
    service = RosterOptimizerService()
    result = service.solve(request)
    
    # Deve ser vazio, pois o cardiologista não pode pegar plantão de clínica geral
    assert len(result) == 0

def test_unavailable_date_constraint(basic_doctors, single_slot):
    """Teste: Médico não pode ser escalado em data marcada como indisponível."""
    # Dr. House está indisponível na data do slot
    target_date = single_slot.date
    basic_doctors[0].availability.unavailable_dates = [target_date]
    
    # Removemos o Dr. Wilson para forçar o teste no Dr. House
    only_house = [basic_doctors[0]] 

    request = OptimizationRequest(
        period_start=target_date, period_end=target_date,
        doctors=only_house, slots_to_fill=[single_slot]
    )
    
    service = RosterOptimizerService()
    result = service.solve(request)
    
    assert len(result) == 0 # Inviável

def test_double_booking_prevention(basic_doctors):
    """Teste: Médico não pode estar em dois lugares ao mesmo tempo."""
    slot_a = ShiftSlot(
        id="slot_uti_a", date=date(2023, 10, 1), shift_type=ShiftTypeEnum.DIURNO,
        required_specialties=[SpecialtyEnum.CLINICA_GERAL], required_count=1, sector_id="UTI A"
    )
    slot_b = ShiftSlot(
        id="slot_uti_b", date=date(2023, 10, 1), shift_type=ShiftTypeEnum.DIURNO, # Mesmo horário
        required_specialties=[SpecialtyEnum.CLINICA_GERAL], required_count=1, sector_id="UTI B"
    )
    
    # Só temos 1 médico disponível (Dr. House)
    only_house = [basic_doctors[0]]
    
    request = OptimizationRequest(
        period_start=date(2023, 10, 1), period_end=date(2023, 10, 1),
        doctors=only_house, slots_to_fill=[slot_a, slot_b]
    )
    
    service = RosterOptimizerService()
    result = service.solve(request)
    
    # O solver deve escolher qual slot preencher, mas não pode preencher os dois
    # Como não definimos prioridade hard de preencher todos, ele preencherá o que der (1)
    # Obs: Se fosse hard constraint preencher todos, retornaria Infeasible (len=0).
    # Na nossa implementação atual, tentamos maximizar, então ele preenche 1.
    assert len(result) <= 1