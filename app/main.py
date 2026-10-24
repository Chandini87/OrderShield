import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  (registers the tables)
from app.database import Base, engine
from app.exceptions import (
    IdempotencyConflict,
    InsufficientStock,
    InvalidTransition,
    OrderNotFound,
    OrderShieldError,
    ProductNotFound,
)
from app.logging_config import log_event, request_id_var, setup_logging
from app.routers import orders, products

setup_logging()
logger = logging.getLogger("ordershield.http")

STATUS_CODES = {
    ProductNotFound: 404,
    OrderNotFound: 404,
    InsufficientStock: 400,
    IdempotencyConflict: 422,
    InvalidTransition: 409,
}

DESCRIPTION = """
A reliable e-commerce order processing backend.

* **Idempotent orders**: send an `Idempotency-Key` header; retrying the same
  request never creates a second order.
* **Safe stock handling**: concurrent buyers can never oversell an item.
* **Failure recovery**: failed payments release reserved stock.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="OrderShield",
    version="1.0.0",
    description=DESCRIPTION,
    lifespan=lifespan,
)

app.include_router(products.router)
app.include_router(orders.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_var.set(request_id)
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    log_event(
        logger, "request_completed",
        method=request.method, path=request.url.path,
        status=response.status_code, duration_ms=duration_ms,
    )
    return response


@app.exception_handler(OrderShieldError)
async def ordershield_error_handler(request: Request, exc: OrderShieldError):
    status = STATUS_CODES.get(type(exc), 400)
    return JSONResponse(
        status_code=status,
        content={"detail": str(exc), "code": exc.code},
    )


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}