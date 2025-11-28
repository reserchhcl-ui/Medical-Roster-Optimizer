from typing import List
from sqlalchemy import select
from app.infrastructure.repositories.base import BaseRepository
from app.infrastructure.orm_models import DoctorORM
from app.domain.models import Doctor

class DoctorRepository(BaseRepository[DoctorORM]):
    def __init__(self, session):
        super().__init__(session, DoctorORM)

    async def create_from_domain(self, doctor: Doctor) -> DoctorORM:
        """Converte Domain Model -> ORM Model"""
        # Pydantic .model_dump(mode='json') serializa datas e enums para string automaticamente
        data = doctor.model_dump(mode='json') 
        
        # Extraímos campos aninhados para colunas JSON
        attributes_data = data.pop('attributes')
        availability_data = data.pop('availability')
        specialties_data = data.pop('specialties')

        db_doctor = DoctorORM(
            id=doctor.id,
            name=doctor.name,
            crm=doctor.crm,
            specialties=specialties_data,
            attributes=attributes_data,
            availability=availability_data
        )
        
        self.session.add(db_doctor)
        await self.session.commit()
        return db_doctor

    async def get_all_active_doctors(self) -> List[Doctor]:
        """Retorna todos os médicos convertidos para o Domain Model"""
        stmt = select(self.model)
        result = await self.session.execute(stmt)
        orm_doctors = result.scalars().all()
        
        domain_doctors = []
        for orm in orm_doctors:
            # Reconstrução do objeto de Domínio a partir do ORM
            # Precisamos mapear de volta os campos JSON para a estrutura plana/aninhada
            doc_dict = {
                "id": orm.id,
                "name": orm.name,
                "crm": orm.crm,
                "specialties": orm.specialties,
                "attributes": orm.attributes,
                "availability": orm.availability
            }
            domain_doctors.append(Doctor(**doc_dict))
            
        return domain_doctors