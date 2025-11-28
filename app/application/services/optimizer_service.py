from typing import List, Dict, Tuple
from ortools.sat.python import cp_model
from app.domain.models import (
    OptimizationRequest, 
    RosterSolution, 
    Doctor, 
    ShiftSlot
)
import math

class RosterOptimizerService:
    def __init__(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

    def solve(self, request: OptimizationRequest) -> List[RosterSolution]:
        self.model = cp_model.CpModel()
        
        # Mapeamentos
        shifts: Dict[Tuple[str, str], cp_model.IntVar] = {}
        doctors_shifts_count: Dict[str, cp_model.IntVar] = {} # Quantos plantões cada médico pegou
        
        # 1. Variáveis de Decisão
        for doctor in request.doctors:
            for slot in request.slots_to_fill:
                shifts[(doctor.id, slot.id)] = self.model.NewBoolVar(f'shift_d{doctor.id}_s{slot.id}')

        # 2. Hard Constraints (Mantivemos as mesmas)
        
        # H1: Preenchimento obrigatório do slot
        for slot in request.slots_to_fill:
            self.model.Add(
                sum(shifts[(doctor.id, slot.id)] for doctor in request.doctors) == slot.required_count
            )

        # H2: Indisponibilidade de Agenda
        for doctor in request.doctors:
            for date_unavailable in doctor.availability.unavailable_dates:
                for slot in request.slots_to_fill:
                    if slot.date == date_unavailable:
                        self.model.Add(shifts[(doctor.id, slot.id)] == 0)

        # H3: Especialidade
        for doctor in request.doctors:
            doctor_specialties_set = set(doctor.specialties)
            for slot in request.slots_to_fill:
                slot_specialties_set = set(slot.required_specialties)
                if not doctor_specialties_set.intersection(slot_specialties_set):
                     self.model.Add(shifts[(doctor.id, slot.id)] == 0)

        # H4: Choque de Horário (Simplificado por data/turno)
        for doctor in request.doctors:
            slots_by_moment = {} 
            for slot in request.slots_to_fill:
                key = (slot.date, slot.shift_type)
                if key not in slots_by_moment: slots_by_moment[key] = []
                slots_by_moment[key].append(slot)
            
            for key, slots_in_moment in slots_by_moment.items():
                if len(slots_in_moment) > 1:
                    self.model.Add(sum(shifts[(doctor.id, s.id)] for s in slots_in_moment) <= 1)

        # H5: Limite Máximo Individual
        for doctor in request.doctors:
            # Cria variável que conta quantos plantões o médico pegou
            count_var = self.model.NewIntVar(0, 31, f'count_{doctor.id}')
            self.model.Add(
                count_var == sum(shifts[(doctor.id, slot.id)] for slot in request.slots_to_fill)
            )
            # Aplica limite do médico
            self.model.Add(count_var <= doctor.availability.max_shifts_per_month)
            
            # Armazena para uso na equidade
            doctors_shifts_count[doctor.id] = count_var

        # ==============================================================================
        # 3. SOFT CONSTRAINTS & OBJETIVOS (A mágica acontece aqui)
        # ==============================================================================
        objective_terms = []

        # S1: Custo (Minimizar)
        # S2: Preferência (Maximizar)
        for doctor in request.doctors:
            for slot in request.slots_to_fill:
                var = shifts[(doctor.id, slot.id)]
                
                # Preferência
                if slot.date in doctor.availability.preferred_dates:
                    objective_terms.append(var * 50 * int(request.weight_preference))
                
                # Custo
                cost = int(doctor.attributes.cost_per_hour * slot.hours_duration)
                objective_terms.append(var * -cost * int(request.weight_cost))

        # S3: Equidade (NOVO!)
        # Queremos penalizar médicos que fogem muito da média ideal.
        # Média Ideal = Total Slots / Total Médicos
        if request.weight_fairness > 0:
            total_slots_needed = sum(s.required_count for s in request.slots_to_fill)
            # Arredondamos para baixo para ter um target inteiro
            avg_target = math.floor(total_slots_needed / len(request.doctors))
            
            for doctor in request.doctors:
                # Vamos penalizar o desvio absoluto da média
                # delta = abs(shifts_count - avg_target)
                
                delta = self.model.NewIntVar(0, 31, f'delta_{doctor.id}')
                count = doctors_shifts_count[doctor.id]
                
                # CP-SAT truque para valor absoluto:
                # delta >= count - avg
                # delta >= avg - count
                self.model.Add(delta >= count - avg_target)
                self.model.Add(delta >= avg_target - count)
                
                # Penalidade quadrática ou linear. Vamos usar linear forte aqui.
                # Quanto maior o peso de equidade, mais ele penaliza o desvio.
                # Multiplicamos por -1000 para ser significativo contra o custo em reais
                penalty = delta * -1000 * int(request.weight_fairness)
                objective_terms.append(penalty)

        # Maximizar Score Total
        self.model.Maximize(sum(objective_terms))

        # ==============================================================================
        # 4. Resolução
        # ==============================================================================
        self.solver.parameters.num_search_workers = 8 
        # Aumentamos um pouco o tempo limite para ele tentar equilibrar
        self.solver.parameters.max_time_in_seconds = 5.0 
        
        status = self.solver.Solve(self.model)
        final_roster = []

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"✅ Status: {self.solver.StatusName(status)} | Obj: {self.solver.ObjectiveValue()}")
            for doctor in request.doctors:
                for slot in request.slots_to_fill:
                    if self.solver.Value(shifts[(doctor.id, slot.id)]) == 1:
                        final_roster.append(RosterSolution(
                            slot_id=slot.id, doctor_id=doctor.id, date=slot.date
                        ))
        
        return final_roster