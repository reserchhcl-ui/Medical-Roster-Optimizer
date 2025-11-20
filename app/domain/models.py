from enum import Enum
from typing import List, Optional, Dict
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

class ShiftTypeEnum(str, Enum):
    DIURNO = "diurno"       # 07:00 - 19:00
    NOTURNO = "noturno"     # 19:00 - 07:00
    MISTO_24H = "misto_24h" # 07:00 - 07:00 (dia seguinte)

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
    """Representa um 'buraco' na escala que precisa ser preenchido"""
    id: str
    date: date
    shift_type: ShiftTypeEnum
    required_specialties: List[SpecialtyEnum]
    required_count: int = Field(1, description="Quantos médicos são necessários neste slot")
    sector_id: str # Ex: "UTI-A", "Emergencia"
    
    @property
    def hours_duration(self) -> int:
        if self.shift_type == ShiftTypeEnum.MISTO_24H:
            return 24
        return 12

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
    weight_fairness: float = 1.5   # Maximizar distribuição igualitária
    
    @validator('period_end')
    def check_dates(cls, v, values):
        if 'period_start' in values and v < values['period_start']:
            raise ValueError('Data final deve ser maior que a inicial')
        return v