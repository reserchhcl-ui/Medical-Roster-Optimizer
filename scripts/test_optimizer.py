import sys
import os
import random
import time
from datetime import date, timedelta
from typing import List

# Setup de path para reconhecer a pasta app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.domain.models import (
    Doctor, DoctorAttributes, DoctorAvailability, 
    ShiftSlot, SpecialtyEnum, ShiftTypeEnum, OptimizationRequest
)
from app.application.services.optimizer_service import RosterOptimizerService

# --- Configurações do Teste de Carga ---
NUM_DOCTORS = 40
DAYS_IN_MONTH = 30
SHIFTS_PER_DAY = 2 # Diurno e Noturno
TOTAL_SLOTS = DAYS_IN_MONTH * SHIFTS_PER_DAY

def generate_random_doctors(n: int, start_date: date, end_date: date) -> List[Doctor]:
    """Gera uma lista heterogênea de médicos com restrições aleatórias"""
    doctors = []
    specialties_pool = [
        SpecialtyEnum.CLINICA_GERAL, 
        SpecialtyEnum.PEDIATRIA, 
        SpecialtyEnum.CARDIOLOGIA
    ]

    print(f"🎲 Gerando {n} médicos com perfis variados...")

    for i in range(1, n + 1):
        # 70% de chance de ser Generalista (necessário para cobrir o grosso da escala)
        specs = [SpecialtyEnum.CLINICA_GERAL]
        if random.random() > 0.7:
            specs.append(random.choice(specialties_pool))
            
        # Nível Senioridade (1 a 5) -> Afeta o custo
        seniority = random.randint(1, 5)
        base_cost = 100.0
        cost = base_cost + (seniority * 50.0) # Senior custa mais

        # Gerar dias indisponíveis aleatórios (Ex: 3 a 8 dias no mês que ele NÃO pode)
        unavailable_count = random.randint(2, 6)
        all_dates = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
        unavailable_dates = random.sample(all_dates, k=min(unavailable_count, len(all_dates)))
        
        # Preferências (Ex: quer trabalhar no dia 15)
        preferred_dates = []
        if random.random() > 0.5:
            preferred_dates.append(start_date + timedelta(days=random.randint(0, 29)))

        # Workload: Alguns querem 4 plantões, outros 12
        max_shifts = random.randint(4, 12)

        doc = Doctor(
            id=f"doc_{i:02d}", 
            name=f"Dr(a). Sobrenome_{i:02d}", 
            crm=f"CRM-{10000+i}",
            specialties=specs,
            attributes=DoctorAttributes(
                seniority_level=seniority, 
                cost_per_hour=cost, 
                is_preceptor=(seniority > 3)
            ),
            availability=DoctorAvailability(
                unavailable_dates=unavailable_dates,
                preferred_dates=preferred_dates,
                max_shifts_per_month=max_shifts
            )
        )
        doctors.append(doc)
    
    return doctors

def generate_month_slots(start_date: date, days: int) -> List[ShiftSlot]:
    """Gera slots complexos misturando 12h e 6h"""
    slots = []
    print(f"📅 Criando grade HÍBRIDA de {days} dias...")
    
    for i in range(days):
        current = start_date + timedelta(days=i)
        
        # Cenário Misto: 
        # Em alguns dias (impares), o hospital quebra o plantão em Manhã/Tarde
        # Em dias pares, mantém o padrão 12h.
        
        if i % 2 != 0: 
            # === DIA DE PLANTÕES QUEBRADOS (Mais flexibilidade) ===
            # Slot Manhã (07-13)
            slots.append(ShiftSlot(
                id=f"slot_{current}_manha", date=current,
                shift_type=ShiftTypeEnum.MANHA,
                required_specialties=[SpecialtyEnum.CLINICA_GERAL],
                required_count=1, sector_id="Emergencia Triagem"
            ))
            # Slot Tarde (13-19)
            slots.append(ShiftSlot(
                id=f"slot_{current}_tarde", date=current,
                shift_type=ShiftTypeEnum.TARDE,
                required_specialties=[SpecialtyEnum.CLINICA_GERAL],
                required_count=1, sector_id="Emergencia Triagem"
            ))
            # Slot Diurno 12h (Simultâneo em outro setor, ex: UTI)
            slots.append(ShiftSlot(
                id=f"slot_{current}_uti_day", date=current,
                shift_type=ShiftTypeEnum.DIURNO, # Colide com Manhã e Tarde se for o mesmo médico
                required_specialties=[SpecialtyEnum.CLINICA_GERAL],
                required_count=1, sector_id="UTI Geral"
            ))
        else:
            # === DIA PADRÃO 12h ===
            slots.append(ShiftSlot(
                id=f"slot_{current}_day", date=current,
                shift_type=ShiftTypeEnum.DIURNO,
                required_specialties=[SpecialtyEnum.CLINICA_GERAL],
                required_count=2, # Precisa de 2 médicos de 12h
                sector_id="Emergencia Geral"
            ))

        # Noturno sempre fixo 12h
        slots.append(ShiftSlot(
            id=f"slot_{current}_night", date=current,
            shift_type=ShiftTypeEnum.NOTURNO,
            required_specialties=[SpecialtyEnum.CLINICA_GERAL],
            required_count=1, sector_id="Plantão Noturno"
        ))
        
    return slots

def analyze_results(solutions, doctors, slots_count, duration):
    """Gera um relatório de inteligência sobre a escala"""
    print("\n" + "="*50)
    print(f"⚡ RELATÓRIO DE PERFORMANCE DA OTIMIZAÇÃO")
    print("="*50)
    
    if not solutions:
        print("❌ FALHA: Nenhuma solução encontrada. O problema é matematicamente impossível com as restrições atuais.")
        return

    # Métricas Básicas
    assigned_slots = len(solutions)
    coverage_percent = (assigned_slots / slots_count) * 100
    
    print(f"⏱️ Tempo de Cálculo: {duration:.4f} segundos")
    print(f"📈 Cobertura da Escala: {coverage_percent:.1f}% ({assigned_slots}/{slots_count})")
    
    # Análise de Custos e Distribuição
    total_cost = 0.0
    shifts_per_doc = {d.id: 0 for d in doctors}
    
    for sol in solutions:
        doc = next(d for d in doctors if d.id == sol.doctor_id)
        shifts_per_doc[doc.id] += 1
        
        # Custo estimado (12h por plantão padrão)
        slot_hours = 12 
        total_cost += doc.attributes.cost_per_hour * slot_hours

    print(f"💰 Custo Total Estimado: R$ {total_cost:,.2f}")
    
    # Análise de Distribuição (Quem trabalhou mais?)
    active_docs = [count for count in shifts_per_doc.values() if count > 0]
    avg_shifts = sum(active_docs) / len(active_docs) if active_docs else 0
    max_shifts = max(shifts_per_doc.values()) if shifts_per_doc.values() else 0
    min_shifts = min(shifts_per_doc.values())
    
    print(f"👥 Médicos Utilizados: {len(active_docs)} de {len(doctors)}")
    print(f"📊 Média de Plantões/Médico: {avg_shifts:.1f}")
    print(f"⚖️ Disparidade: Mínimo {min_shifts} - Máximo {max_shifts} plantões")
    
    print("\n🔍 TOP 5 Médicos Mais Escalados:")
    sorted_docs = sorted(shifts_per_doc.items(), key=lambda item: item[1], reverse=True)[:5]
    for doc_id, count in sorted_docs:
        doc_name = next(d.name for d in doctors if d.id == doc_id)
        print(f"   - {doc_name}: {count} plantões")

def run_stress_test():
    start_date = date(2023, 10, 1)
    end_date = start_date + timedelta(days=DAYS_IN_MONTH - 1)

    # 1. Preparar Dados
    doctors = generate_random_doctors(NUM_DOCTORS, start_date, end_date)
    slots = generate_month_slots(start_date, DAYS_IN_MONTH)

    # 2. Montar Request
    # Weight Cost alto força o sistema a tentar pegar os médicos mais baratos (Jrs)
    # Weight Preference força o sistema a respeitar os pedidos
    request = OptimizationRequest(
        period_start=start_date,
        period_end=end_date,
        doctors=doctors,
        slots_to_fill=slots,
        weight_cost=1.0,       # Custo importa normal
        weight_preference=1.0, # Preferência importa normal
        weight_fairness=5.0    # 🔥 FORÇAR DISTRIBUIÇÃO IGUALITÁRIA
    )

    optimizer = RosterOptimizerService()

    # 3. Executar com cronômetro
    print(f"\n🚀 Iniciando Motor de Otimização (Google CP-SAT)...")
    print(f"   Matriz: {len(doctors)} Médicos x {len(slots)} Slots = {len(doctors)*len(slots)} Variáveis de Decisão")
    
    start_time = time.time()
    solutions = optimizer.solve(request)
    end_time = time.time()

    # 4. Análise
    analyze_results(solutions, doctors, len(slots), end_time - start_time)

if __name__ == "__main__":
    run_stress_test()