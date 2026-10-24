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
from app.routers import orders, products

STATUS_CODES = {
    ProductNotFound: 404,
    OrderNotFound: 404,
    InsufficientStock: 400,
    IdempotencyConflict: 422,
    InvalidTransition: 409,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="OrderShield", version="0.2.0", lifespan=lifespan)

app.include_router(products.router)
app.include_router(orders.router)


@app.exception_handler(OrderShieldError)
async def ordershield_error_handler(request: Request, exc: OrderShieldError):
    code = STATUS_CODES.get(type(exc), 400)
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}