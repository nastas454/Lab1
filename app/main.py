import time
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, Query, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, engine
from app.models import DispensaryRecord
from app.schemas import DispensaryCreate, DispensaryOut, DispensaryListOut
import os
import socket

POD_NAME = os.getenv("POD_NAME", socket.gethostname())

REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "code"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.002, 0.005, 0.010, 0.020, 0.050, 0.100, 0.200, 0.500, 1.000, 2.000]
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "path"]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
app = FastAPI(lifespan=lifespan)


# --- 3. Проміжний обробник (middleware) для метрик та X-Pod ---
@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    method = request.method

    # Визначаємо шаблон шляху (наприклад, /dispensary/{id} замість /dispensary/123)[cite: 8]
    path_template = request.url.path
    if "route" in request.scope:
        path_template = request.scope["route"].path

    REQUESTS_IN_PROGRESS.labels(method=method, path=path_template).inc()
    start_time = time.time()

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        response.headers["X-Pod"] = POD_NAME
    except Exception as e:
        status_code = "500"
        raise e
    finally:
        duration = time.time() - start_time
        REQUEST_DURATION.labels(method=method, path=path_template).observe(duration)
        REQUEST_COUNTER.labels(method=method, path=path_template, code=status_code).inc()
        REQUESTS_IN_PROGRESS.labels(method=method, path=path_template).dec()

    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc.errors())}
    )


# --- 4. Ендпоінти для метрик та healthcheck ---
@app.get("/metrics")
def get_metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/livez", status_code=status.HTTP_200_OK)
def livez():
    return {"status": "ok"}


@app.get("/healthz", status_code=status.HTTP_200_OK)
async def healthcheck(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(1))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="DB unavailable")


# --- 5. Ваші бізнес-ендпоінти (CRUD) ---
@app.post("/dispensary", response_model=DispensaryOut, status_code=status.HTTP_201_CREATED)
async def create_record(record: DispensaryCreate, db: AsyncSession = Depends(get_db)):
    db_record = DispensaryRecord(**record.model_dump())
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)
    return db_record


@app.get("/dispensary", response_model=DispensaryListOut)
async def get_records(
        accounting_group: Optional[str] = None,
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