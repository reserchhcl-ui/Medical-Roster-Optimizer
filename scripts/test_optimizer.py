import sys
import os
from datetime import date, timedelta

# Adiciona o diretório raiz ao path para importar os módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.domain.models import (
    Doctor, DoctorAttributes, DoctorAvailability, 
    ShiftSlot, SpecialtyEnum, ShiftTypeEnum, OptimizationRequest
)
from app.application.services.optimizer_service import RosterOptimizerService

def run_test():
    print("🏥 Gerando dados de teste para Otimização de Escala...")

    # 1. Criar Médicos (Mock)
    doctors = []
    
    # Dr. House (Caro, Clinico, odeia trabalhar as segundas)
    doc1 = Doctor(
        id="doc_1", name="Dr. Gregory House", crm="12345",
        specialties=[SpecialtyEnum.CLINICA_GERAL, SpecialtyEnum.DIAGNOSTICO], # Adicionei Diagnostico mentalmente
        attributes=DoctorAttributes(seniority_level=5, cost_per_hour=500.0, is_preceptor=True),
        availability=DoctorAvailability(
            unavailable_dates=[date(2023, 10, 2)], # Segunda-feira
            preferred_dates=[date(2023, 10, 5)],
            max_shifts_per_month=5
        )
    )
    
    # Dra. Cameron (Pediatra, mais barata, alta disponibilidade)
    doc2 = Doctor(
        id="doc_2", name="Dra. Allison Cameron", crm="54321",
        specialties=[SpecialtyEnum.PEDIATRIA, SpecialtyEnum.CLINICA_GERAL],
        attributes=DoctorAttributes(seniority_level=2, cost_per_hour=200.0, is_preceptor=False),
        availability=DoctorAvailability(
            unavailable_dates=[],
            preferred_dates=[date(2023, 10, 1), date(2023, 10, 2)],
            max_shifts_per_month=20
        )
    )

    # Dr. Foreman (Neurologista/Clinico, intermediário)
    doc3 = Doctor(
        id="doc_3", name="Dr. Eric Foreman", crm="98765",
        specialties=[SpecialtyEnum.CLINICA_GERAL],
        attributes=DoctorAttributes(seniority_level=3, cost_per_hour=300.0, is_preceptor=False),
        availability=DoctorAvailability(
            unavailable_dates=[date(2023, 10, 5)],
            max_shifts_per_month=10
        )
    )

    doctors = [doc1, doc2, doc3]

    # 2. Criar Slots (Buracos na escala a preencher)
    slots = []
    start_date = date(2023, 10, 1)
    
    # Vamos criar uma semana de plantões para Clinica Geral
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        
        # Plantão Diurno - Precisa de 1 Clinico
        slots.append(ShiftSlot(
            id=f"slot_{current_date}_day",
            date=current_date,
            shift_type=ShiftTypeEnum.DIURNO,
            required_specialties=[SpecialtyEnum.CLINICA_GERAL],
            required_count=1,
            sector_id="Emergencia"
        ))

        # Plantão Noturno - Precisa de 1 Clinico
        slots.append(ShiftSlot(
            id=f"slot_{current_date}_night",
            date=current_date,
            shift_type=ShiftTypeEnum.NOTURNO,
            required_specialties=[SpecialtyEnum.CLINICA_GERAL],
            required_count=1,
            sector_id="Emergencia"
        ))

    # 3. Montar Request
    request = OptimizationRequest(
        period_start=start_date,
        period_end=start_date + timedelta(days=6),
        doctors=doctors,
        slots_to_fill=slots,
        weight_cost=2.0, # Priorizar economia
        weight_preference=1.5
    )

    # 4. Executar Otimizador
    optimizer = RosterOptimizerService()
    try:
        print("⚙️  Rodando Google OR-Tools CP-SAT...")
        result = optimizer.solve(request)
        
        print(f"\n📊 Resultado Final: {len(result)} plantões alocados de {len(slots)} necessários.")
        
        # Exibir escala legível
        result.sort(key=lambda x: x.date)
        print("\n--- ESCALA GERADA ---")
        for entry in result:
            doc_name = next(d.name for d in doctors if d.id == entry.doctor_id)
            print(f"📅 {entry.date} | Slot: {entry.slot_id} -> 👨‍⚕️ {doc_name}")

    except Exception as e:
        print(f"🔥 Erro crítico: {e}")

if __name__ == "__main__":
    run_test()