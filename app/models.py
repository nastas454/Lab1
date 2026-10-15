import uuid
from sqlalchemy import Column, String, Integer, Date
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class DispensaryRecord(Base):
    __tablename__ = "dispensary"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_code = Column(String, nullable=False)
    accounting_group = Column(String, nullable=False, index=True)
    registration_date = Column(Date, nullable=False)
    periodicity_months = Column(Integer, nullable=False)
    last_examination_date = Column(Date, nullable=False)