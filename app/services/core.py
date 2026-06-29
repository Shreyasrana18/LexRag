from sqlalchemy import select
import app.pipelines.parser as parser
import app.db.qdrant as qdrant
import app.services.embedding as embedder
import app.services.llm as llm
import app.pipelines.utils as utils
from app.constants import WEAK_RESPONSE_PHRASES
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Case, CaseChunk, ChatSession, ChatMessage
from app.services import reranker
from datetime import datetime
from fastapi.responses import StreamingResponse
from app.worker.pool import get_arq_pool 
from app.constants import CHAT_HISTORY_LIMIT, ERROR_RESPONSES
import uuid
import json


async def processUpload(validated_bytes: bytes, db: AsyncSession):
    extracted_metadata = parser.extractMetaData(validated_bytes)
    metadata = extracted_metadata["metadata"]

    try:
        new_case = Case(
            **metadata,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(new_case)
        await db.flush()
        await db.commit()
        await db.refresh(new_case)

        # enqueue processing job
        pool = get_arq_pool()
        await pool.enqueue_job("process_upload", str(new_case.id), validated_bytes)

        return {
            "case_id": new_case.id,
            "status": "pending",
        }

    except Exception as e:
        await db.rollback()
        raise RuntimeError(f"Upload failed: {e}") from e
async def search(db: AsyncSession, q: str, stream: bool = False, case_id: str | None = None, session_id: str | None = None):
    queryEmbeddings = await embedder.generateEmbeddingsAsync(q)

    if not case_id:
        summary_results = await qdrant.search_summaries(query_vector=queryEmbeddings)
        if not summary_results:
            return {"message": "No relevant cases found for your query."}

        case_ids = [r["case_id"] for r in summary_results]
        summaries_map = {r["case_id"]: r["short_summary"] for r in summary_results}

        cases_result = await db.execute(
            select(Case).where(Case.id.in_([uuid.UUID(cid) for cid in case_ids]))
        )
        cases_list = cases_result.scalars().all()

        message = await llm.generateCaseSelectionMessage(q, [
            {"title": case.title, "short_summary": summaries_map.get(str(case.id), "")}
            for case in cases_list
        ])

        return {
            "message": message,
            "cases": [
                {
                    "case_id": str(case.id),
                    "title": case.title,
                    "court": case.court,
                    "case_number": case.case_number,
                    "decision_date": str(case.decision_date),
                    "summary": summaries_map.get(str(case.id), "")
                }
                for case in cases_list
            ]
        }

    if not session_id:
        new_session = ChatSession(
            case_id=case_id,
            created_at=datetime.utcnow()
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        session_id = str(new_session.id)

    chat_messages = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(CHAT_HISTORY_LIMIT)
    )
    chat_history = utils.formatChatHistory(reversed(chat_messages.scalars().all()))

    # fetch more chunks than needed, rerank down to top 5
    chunks = await qdrant.search_chunks(query_vector=queryEmbeddings, case_ids=[case_id], limit=15)
    chunks_for_reranking = [
        {
            "text": chunk.payload["text"],
            "chunk_index": chunk.payload.get("chunk_index"),
            "page_range": chunk.payload.get("page_range", ""),
            "case_id": chunk.payload.get("case_id"),
        }
        for chunk in chunks if chunk.payload
    ]
    reranked_chunks = await reranker.rerank(query=q, chunks=chunks_for_reranking, top_k=5)

    prompt = llm.buildPrompt(reranked_chunks, q, chat_history)

    db.add(ChatMessage(
        session_id=session_id,
        role="user",
        content=q,
        created_at=datetime.utcnow()
    ))
    await db.commit()

    async def stream_and_save():
        full_response = []
        async for chunk in llm.safe_stream(llm.llmsearch(prompt, stream)):
            full_response.append(chunk)
            yield chunk

        full_text = "".join(full_response)
        is_error = any(phrase in full_text.lower() for phrase in WEAK_RESPONSE_PHRASES) or full_text.strip() in ERROR_RESPONSES

        if not is_error:
            db.add(ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_text,
                created_at=datetime.utcnow()
            ))
            await db.commit()
            citations = utils.extract_citations(full_text, reranked_chunks)
            if citations:
                yield f"\n\n###CITATIONS###{json.dumps({'citations': citations})}"    

    return StreamingResponse(
        stream_and_save(),
        media_type="text/plain",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Transfer-Encoding": "chunked",
            "X-Session-Id": session_id
        }
    )