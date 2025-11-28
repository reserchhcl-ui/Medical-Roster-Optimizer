from typing import List, Dict, Tuple
from ortools.sat.python import cp_model
from app.domain.models import (
    OptimizationRequest, 
    RosterSolution, 
    Doctor, 
    ShiftSlot, 
    ShiftTypeEnum
)

class RosterOptimizerService:
    def __init__(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

    def solve(self, request: OptimizationRequest) -> List[RosterSolution]:
        """
        Executa o motor de otimização CP-SAT para gerar a escala.
        """
        # 1. Limpeza do estado do modelo para nova execução
        self.model = cp_model.CpModel()

        # Estruturas de dados auxiliares para mapeamento
        # shifts[(doctor_id, slot_id)] = variavel_booleana_do_solver
        shifts: Dict[Tuple[str, str], cp_model.IntVar] = {}
        
        # Dicionários para acesso rápido aos objetos
        doctors_map = {d.id: d for d in request.doctors}
        slots_map = {s.id: s for s in request.slots_to_fill}
        # ==============================================================================
        # 2. CRIAÇÃO DAS VARIÁVEIS DE DECISÃO
        # ==============================================================================
        for doctor in request.doctors:
            for slot in request.slots_to_fill:
                # Cria uma variável booleana: 1 se o médico trabalha no slot, 0 caso contrário
                shifts[(doctor.id, slot.id)] = self.model.NewBoolVar(f'shift_d{doctor.id}_s{slot.id}')

        # ==============================================================================
        # 3. DEFINIÇÃO DAS HARD CONSTRAINTS (Restrições Obrigatórias)
        # ==============================================================================

        # --- H1: Cada slot deve ter exatamente a quantidade necessária de médicos ---
        for slot in request.slots_to_fill:
            self.model.Add(
                sum(shifts[(doctor.id, slot.id)] for doctor in request.doctors) == slot.required_count
            )

        # --- H2: Respeitar Datas Indisponíveis do Médico ---
        for doctor in request.doctors:
            for date_unavailable in doctor.availability.unavailable_dates:
                for slot in request.slots_to_fill:
                    if slot.date == date_unavailable:
                        self.model.Add(shifts[(doctor.id, slot.id)] == 0)

        # --- H3: Validação de Especialidade ---
        # O médico só pega o plantão se tiver UMA das especialidades requeridas pelo slot
        for doctor in request.doctors:
            doctor_specialties_set = set(doctor.specialties)
            for slot in request.slots_to_fill:
                slot_specialties_set = set(slot.required_specialties)
                # Se a interseção for vazia, o médico não tem a competência necessária
                if not doctor_specialties_set.intersection(slot_specialties_set):
                     self.model.Add(shifts[(doctor.id, slot.id)] == 0)

        # --- H4: Um médico só pode estar em UM lugar por vez no mesmo dia/horário ---
        # Simplificação: Vamos assumir que slots na mesma data colidem se forem do mesmo tipo
        # Em um sistema real, verificaríamos sobreposição de horas exatas.

        for doctor in request.doctors:
            # Agrupar slots por data e período (ex: dia 01/01, noturno)
            # Se houver múltiplos slots simultâneos em setores diferentes (UTI A, UTI B), ele só pode pegar 1
            slots_by_moment = {} 
            for slot in request.slots_to_fill:
                key = (slot.date, slot.shift_type)
                if key not in slots_by_moment:
                    slots_by_moment[key] = []
                slots_by_moment[key].append(slot)
            
            for key, slots_in_moment in slots_by_moment.items():
                if len(slots_in_moment) > 1:
                    self.model.Add(
                        sum(shifts[(doctor.id, s.id)] for s in slots_in_moment) <= 1
                    )

        # --- H5: Limite máximo de plantões por mês (Burnout prevention) ---
        for doctor in request.doctors:
            self.model.Add(
                sum(shifts[(doctor.id, slot.id)] for slot in request.slots_to_fill) <= doctor.availability.max_shifts_per_month
            )

        # ==============================================================================
        # 4. DEFINIÇÃO DAS SOFT CONSTRAINTS (Objetivos a Maximizar/Minimizar)
        # ==============================================================================
        
        # Vamos criar termos de penalidade/recompensa para a função objetivo
        objective_terms = []

        for doctor in request.doctors:
            for slot in request.slots_to_fill:
                var = shifts[(doctor.id, slot.id)]

                # --- S1: Preferência de Data ---
                if slot.date in doctor.availability.preferred_dates:
                    # Recompensa alta se for escalado no dia que quer
                    objective_terms.append(var * 50 * int(request.weight_preference))
                
                # --- S2: Senioridade/Custo (Simplificado) ---
                # Tentar escalar médicos mais seniors/caros apenas quando necessário? 
                # Ou preferir seniors em postos críticos?
                # Aqui vamos tentar minimizar o custo total
                cost = int(doctor.attributes.cost_per_hour * slot.hours_duration)
                # Subtrai do objetivo (porque queremos MAXIMIZAR o objetivo, então custo negativo ajuda)
                objective_terms.append(var * -cost * int(request.weight_cost))

        # Equidade (Fairness) - Avançado
        # Para distribuir igualmente, penalizamos o quadrado da diferença da média (desvio padrão).
        # Para este MVP, vamos manter simples focando em preencher slots e preferências.

        # Define o objetivo: Maximizar a soma dos termos
        self.model.Maximize(sum(objective_terms))

        # ==============================================================================
        # 5. RESOLUÇÃO E OUTPUT
        # ==============================================================================
        # Configurar solver para usar todos os cores
        self.solver.parameters.num_search_workers = 2 
        status = self.solver.Solve(self.model)

        final_roster = []
        print("!!!")
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"✅ Solução Encontrada! Status: {self.solver.StatusName(status)}")
            print(f"🎯 Valor da Função Objetivo: {self.solver.ObjectiveValue()}")
            
            for doctor in request.doctors:
                for slot in request.slots_to_fill:
                    if self.solver.Value(shifts[(doctor.id, slot.id)]) == 1:
                        solution = RosterSolution(
                            slot_id=slot.id,
                            doctor_id=doctor.id,
                            date=slot.date,
                            is_extra_shift=False # Lógica futura
                        )
                        final_roster.append(solution)
        else:
            print("❌ Nenhuma solução viável encontrada. Verifique as restrições.")
            # Em produção, aqui lançaríamos uma Exception customizada detalhando o conflito
        
        return final_roster