from typing import Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct
)
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    QDRANT_URL: str
    QDRANT_COLLECTION_NAME: str
    QDRANT_SUMMARY_COLLECTION_NAME: str
    QDRANT_VECTOR_SIZE: int

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings() # type: ignore
qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)

class DbConfig:
    COLLECTION_NAME = settings.QDRANT_COLLECTION_NAME
    SUMMARY_COLLECTION_NAME = settings.QDRANT_SUMMARY_COLLECTION_NAME
    VECTOR_SIZE = settings.QDRANT_VECTOR_SIZE
    DISTANCE = Distance.COSINE

async def health_check():
    collection = await qdrant_client.get_collections()
    return "ok" if collection else "error"

async def create_collection():
    collections_response = await qdrant_client.get_collections()
    existing = [c.name for c in collections_response.collections]

    for name in [DbConfig.COLLECTION_NAME, DbConfig.SUMMARY_COLLECTION_NAME]:
        if name not in existing:
            await qdrant_client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=DbConfig.VECTOR_SIZE,
                    distance=DbConfig.DISTANCE,
                )
            )

async def upsert_chunk_vector(chunk_id: str, vector: list, payload: dict):
    await qdrant_client.upsert(
        collection_name=DbConfig.COLLECTION_NAME,
        points=[
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload=payload,
            )
        ],
    )

async def search(query_vector: list, limit: int = 5, case_id: Optional[str] = None):
    query_filter = None
    if case_id:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="case_id",
                    match=MatchValue(value=case_id),
                )
            ]
        )
    results = await qdrant_client.query_points(
        collection_name=DbConfig.COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
    )
    return results.points

async def upsert_summary_vector(case_id: str, vector: list, payload: dict):
    # payload should include:
    # {
    #     "case_id": "...",
    #     "summary": "full summary text here"
    # }
    await qdrant_client.upsert(
        collection_name=DbConfig.SUMMARY_COLLECTION_NAME,
        points=[
            PointStruct(
                id=case_id, 
                vector=vector,
                payload=payload,
            )
        ],
    )

async def search_summaries(query_vector: list, limit: int = 5) -> list[str]:
    results = await qdrant_client.query_points(
        collection_name=DbConfig.SUMMARY_COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    )
    return [point.payload["case_id"] for point in results.points if point.payload]

async def search_chunks(query_vector: list, case_ids: list[str], limit: int = 5):
    query_filter = Filter(
        must=[
            FieldCondition(
                key="case_id",
                match=MatchValue(value=case_id),
            )
            for case_id in case_ids
        ]
    ) if case_ids else None

    results = await qdrant_client.query_points(
        collection_name=DbConfig.COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
    )
    return results.points