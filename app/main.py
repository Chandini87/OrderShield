from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers the tables)
from app.database import Base, engine
from app.routers import orders, products


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # create tables on startup
    yield


app = FastAPI(title="OrderShield", version="0.1.0", lifespan=lifespan)

app.include_router(products.router)
app.include_router(orders.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}