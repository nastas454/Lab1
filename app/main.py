from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine, Base, get_db
from app.models import DispensaryRecord
from app.schemas import DispensaryCreate, DispensaryOut, DispensaryListOut

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc.errors())}
    )

@app.post("/dispensary", response_model=DispensaryOut, status_code=status.HTTP_201_CREATED)
async def create_record(record: DispensaryCreate, db: AsyncSession = Depends(get_db)):
    db_record = DispensaryRecord(**record.model_dump())
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)
    return db_record

@app.get("/dispensary", response_model=DispensaryListOut)
async def get_records(
        accounting_group: Optional[str] = None,  # Фільтр за групою[cite: 1]
        limit: int = Query(10, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db)
):
    query = select(DispensaryRecord)
    if accounting_group:
        query = query.where(DispensaryRecord.accounting_group == accounting_group)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return {"items": result.scalars().all(), "total": total}

@app.get("/dispensary/{id}", response_model=DispensaryOut)
async def get_record(id: UUID, db: AsyncSession = Depends(get_db)):
    record = await db.scalar(select(DispensaryRecord).where(DispensaryRecord.id == id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return record

@app.put("/dispensary/{id}", response_model=DispensaryOut)
async def update_record(id: UUID, record_in: DispensaryCreate, db: AsyncSession = Depends(get_db)):
    db_record = await db.scalar(select(DispensaryRecord).where(DispensaryRecord.id == id))
    if not db_record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in record_in.model_dump().items():
        setattr(db_record, key, value)
    await db.commit()
    await db.refresh(db_record)
    return db_record

@app.delete("/dispensary/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(id: UUID, db: AsyncSession = Depends(get_db)):
    db_record = await db.scalar(select(DispensaryRecord).where(DispensaryRecord.id == id))
    if not db_record:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(db_record)
    await db.commit()
    return None

@app.get("/healthz", status_code=status.HTTP_200_OK)
async def healthcheck(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(1))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="DB unavailable")