from enum import Enum
from typing import List, Optional, Dict,Tuple
from datetime import datetime, date
from pydantic import BaseModel, Field, validator

# --- Enums para Padronização ---

class SpecialtyEnum(str, Enum):
    CLINICA_GERAL = "clinica_geral"
    PEDIATRIA = "pediatria"
    CARDIOLOGIA = "cardiologia"
    ORTOPEDIA = "ortopedia"
    ANESTESIOLOGIA = "anestesiologia"
    CIRURGIA = "cirurgia"
    DIAGNOSTICO = "diagnostico"

class ShiftTypeEnum(str, Enum):
    DIURNO = "diurno"       # 07:00 - 19:00 (12h)
    NOTURNO = "noturno"     # 19:00 - 07:00 (12h)
    MANHA = "manha"         # 07:00 - 13:00 (6h) - NOVO
    TARDE = "tarde"         # 13:00 - 19:00 (6h) - NOVO
    MISTO_24H = "misto_24h" # 07:00 - 07:00 (24h)

# --- Entidades Principais ---

class DoctorAttributes(BaseModel):
    """Atributos específicos do médico para pontuação no algoritmo"""
    seniority_level: int = Field(1, ge=1, le=5, description="Nível de senioridade (1-5)")
    is_preceptor: bool = Field(False, description="Se é preceptor de residência")
    cost_per_hour: float = Field(..., gt=0, description="Custo hora do médico")

class DoctorAvailability(BaseModel):
    """Define quando o médico NÃO pode trabalhar ou prefere trabalhar"""
    unavailable_dates: List[date] = []
    preferred_dates: List[date] = []
    max_shifts_per_month: int = Field(10, le=31)
    
    # Restrição Hard: Não pode trabalhar nestes dias da semana (0=Seg, 6=Dom)
    blocked_weekdays: List[int] = [] 

class Doctor(BaseModel):
    id: str
    name: str
    crm: str
    specialties: List[SpecialtyEnum]
    attributes: DoctorAttributes
    availability: DoctorAvailability
    
    class Config:
        from_attributes = True

class ShiftSlot(BaseModel):
    id: str
    date: date
    shift_type: ShiftTypeEnum
    required_specialties: List[str] # Simplificando para string para evitar erro de import circular se houver
    required_count: int = Field(1, description="Quantos médicos são necessários neste slot")
    sector_id: str
    
    @property
    def time_interval(self) -> Tuple[int, int]:
        """
        Retorna (hora_inicio, hora_fim) baseada em inteiros de 0 a 48.
        Usamos >24 para tratar a virada da noite se necessário, 
        mas para colisão diária simples, vamos padronizar:
        """
        mapping = {
            ShiftTypeEnum.MANHA: (7, 13),
            ShiftTypeEnum.TARDE: (13, 19),
            ShiftTypeEnum.DIURNO: (7, 19),
            ShiftTypeEnum.NOTURNO: (19, 31), # 19h até 07h do dia seguinte (19+12)
            ShiftTypeEnum.MISTO_24H: (7, 31) # 07h até 07h do dia seguinte
        }
        return mapping.get(self.shift_type, (0, 0))

    @property
    def hours_duration(self) -> int:
        start, end = self.time_interval
        return end - start

class RosterSolution(BaseModel):
    """Saída do algoritmo: Qual médico pega qual slot"""
    slot_id: str
    doctor_id: str
    date: date
    is_extra_shift: bool = False

class OptimizationRequest(BaseModel):
    """Payload enviado para o motor de otimização"""
    period_start: date
    period_end: date
    doctors: List[Doctor]
    slots_to_fill: List[ShiftSlot]
    
    # Pesos para a função objetivo (Soft Constraints)
    weight_cost: float = 1.0       # Minimizar custo
    weight_preference: float = 2.0 # Maximizar preferência do médico
    weight_fairness: float = 0.0   # Maximizar distribuição igualitária
    
    @validator('period_end')
    def check_dates(cls, v, values):
        if 'period_start' in values and v < values['period_start']:
            raise ValueError('Data final deve ser maior que a inicial')
        return v