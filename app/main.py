from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.qdrant import create_collection, health_check
from app.db.postgres import health_check as db_health_check
from app.api.routes import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    await create_collection()
    print("Application startup complete.")
    yield
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

app.include_router(api_router, prefix="/api")
@app.get("/health")
async def root():
    return {
        "status": "ok",
        "qdrant_health": health_check(),
        "postgres_health": await db_health_check()
    }