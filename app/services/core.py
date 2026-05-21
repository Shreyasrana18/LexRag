from sqlalchemy import select
import app.pipelines.parser as parser
import app.db.qdrant as qdrant
import app.services.embedding as embedder
import app.services.llm as llm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Case, CaseChunk
from datetime import datetime
from fastapi.responses import StreamingResponse


async def processUpload(validated_bytes: bytes, db: AsyncSession):
    extracted_metadata = parser.extractMetaData(validated_bytes)
    extracted_paragraphs = parser.extractParagraphs(validated_bytes)
    metadata = extracted_metadata["metadata"]

    try:
        # 1. Save Case to Postgres
        new_case = Case(
            **metadata,
            created_at=datetime.utcnow(),
        )
        db.add(new_case)
        await db.flush()

        # 2. Save CaseChunks to Postgres
        chunks = [
            CaseChunk(
                case_id=new_case.id,
                chunk_index=i,
                text=paragraph,
                created_at=datetime.utcnow(),
            )
            for i, paragraph in enumerate(extracted_paragraphs)
        ]
        db.add_all(chunks)
        await db.flush()

        # 3. Generate embeddings and upsert to Qdrant
        for chunk in chunks:
            vector = await embedder.generateEmbeddingsAsync(chunk.text)
            await qdrant.upsert_chunk_vector(
                chunk_id=str(chunk.id),
                vector=vector,
                payload={
                    "case_id": str(new_case.id),
                    "chunk_index": chunk.chunk_index
                }
            )

        await db.commit()
        await db.refresh(new_case)

        return {
            "metadata": extracted_metadata,
            "case_id": new_case.id,
        }

    except Exception as e:
        await db.rollback()
        raise RuntimeError(f"Upload failed, transaction rolled back: {e}") from e
    

async def search(db: AsyncSession, q: str, stream: bool = False, case_id: str | None = None):
    queryEmbeddings = await embedder.generateEmbeddingsAsync(q)
    results = await qdrant.search(query_vector=queryEmbeddings, case_id=case_id)
    case_ids = [
        result.payload['case_id']
        for result in results
        if result.payload is not None             
    ]
    case_chunks = await db.execute(
        select(CaseChunk.text).where(CaseChunk.case_id.in_(case_ids))
    )
    texts: list[str] = list(case_chunks.scalars().all())
    prompt = llm.buildPrompt(texts, q)
    return StreamingResponse(
            llm.safe_stream(llm.llmsearch(prompt, stream)),
            media_type="text/plain",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Transfer-Encoding": "chunked"}
        )