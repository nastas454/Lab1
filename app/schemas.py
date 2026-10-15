from pydantic import BaseModel, Field
from datetime import date
from typing import List
from uuid import UUID

class DispensaryBase(BaseModel):
    patient_code: str
    accounting_group: str
    registration_date: date
    periodicity_months: int = Field(..., ge=1, le=24)
    last_examination_date: date

class DispensaryCreate(DispensaryBase):
    pass

class DispensaryOut(DispensaryBase):
    id: UUID

    class Config:
        from_attributes = True

class DispensaryListOut(BaseModel):
    items: List[DispensaryOut]
    total: int