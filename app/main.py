from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.qdrant import create_collection, health_check
from app.db.postgres import health_check as db_health_check
from app.api.routes import router as api_router
from arq.connections import create_pool, RedisSettings
import app.worker.pool as worker_pool
from app.worker.pool import health_check as redis_health_check

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    await create_collection()
    worker_pool.arq_pool = await create_pool(RedisSettings(host="localhost", port=6379))
    print("Application startup complete.")
    yield
    await worker_pool.arq_pool.close()
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)
app.include_router(api_router, prefix="/api")

@app.get("/health")
async def root():
    return {
        "status": "ok",
        "qdrant_health": await health_check(),
        "postgres_health": await db_health_check(),
        "redis_health": await redis_health_check()
    }