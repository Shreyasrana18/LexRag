from app.db.postgres import AsyncSessionLocal
from app.db.models import Case
from app.db import qdrant
from app.services import embedding, llm
from app.pipelines import parser
import uuid

async def process_upload(ctx: dict, case_id: str, pdf_bytes: bytes):
    async with AsyncSessionLocal() as db:
        case = await db.get(Case, uuid.UUID(case_id))
        if not case:
            raise RuntimeError(f"Case {case_id} not found")
        try:
            # update status to processing
            case.status = "processing"
            await db.commit()

            # 1. extract 2-page chunks
            chunks = parser.extractPages(pdf_bytes)

            rolling_summary = ""
            for i, chunk_text in enumerate(chunks):
                # 2. embed and upsert chunk to qdrant
                vector = await embedding.generateEmbeddingsAsync(chunk_text)
                await qdrant.upsert_chunk_vector(
                    chunk_id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "case_id": case_id,
                        "chunk_index": i,
                        "text": chunk_text,
                    }
                )

                # 3. update rolling summary via LLM
                rolling_summary = await llm.llmsummarize(rolling_summary, chunk_text)

            # 4. embed and upsert final summary
            summary_vector = await embedding.generateEmbeddingsAsync(rolling_summary)
            await qdrant.upsert_summary_vector(
                case_id=case_id,
                vector=summary_vector,
                payload={
                    "case_id": case_id,
                    "summary": rolling_summary,
                }
            )

            # 5. mark done
            case.status = "done"
            await db.commit()
        except Exception as e:
            case.status = "failed"
            await db.commit()
            raise RuntimeError(f"Processing failed for case {case_id}: {e}") from e