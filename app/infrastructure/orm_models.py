from sqlalchemy import Column, String, Integer, Boolean, Date, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class DoctorORM(Base):
    __tablename__ = "doctors"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    crm = Column(String, unique=True, nullable=False)
    
    # Armazenamos listas de Enums como JSON array: ["clinica_geral", "cardiologia"]
    specialties = Column(JSON, nullable=False)
    
    # Armazenamos os objetos aninhados como JSON para performance de leitura
    # Mapeia: DoctorAttributes e DoctorAvailability
    attributes = Column(JSON, nullable=False)
    availability = Column(JSON, nullable=False)

    # Relacionamentos
    assigned_shifts = relationship("RosterSolutionORM", back_populates="doctor")

class ShiftSlotORM(Base):
    __tablename__ = "shift_slots"

    id = Column(String, primary_key=True, default=generate_uuid)
    date = Column(Date, nullable=False)
    shift_type = Column(String, nullable=False) # "diurno", "noturno"
    required_specialties = Column(JSON, nullable=False)
    required_count = Column(Integer, default=1)
    sector_id = Column(String, nullable=False)

    # Relacionamentos
    allocation = relationship("RosterSolutionORM", back_populates="slot")

class RosterSolutionORM(Base):
    __tablename__ = "roster_solutions"

    # Chave composta pode ser usada, mas ID surrogate é mais fácil para ORMs
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    slot_id = Column(String, ForeignKey("shift_slots.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    date = Column(Date, nullable=False)
    is_extra_shift = Column(Boolean, default=False)
    created_at = Column(Date, nullable=True) # Metadado de auditoria

    doctor = relationship("DoctorORM", back_populates="assigned_shifts")
    slot = relationship("ShiftSlotORM", back_populates="allocation")