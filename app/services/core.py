from sqlalchemy import select
import app.pipelines.parser as parser
import app.db.qdrant as qdrant
import app.services.embedding as embedder
import app.services.llm as llm
import app.pipelines.utils as utils
from app.constants import WEAK_RESPONSE_PHRASES
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Case, CaseChunk, ChatSession, ChatMessage
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
    

async def search(db: AsyncSession, q: str, stream: bool = False, case_id: str | None = None, session_id: str | None = None):
    queryEmbeddings = await embedder.generateEmbeddingsAsync(q)

    if not session_id:
        new_session = ChatSession(
            case_id=case_id if case_id else None,
            created_at=datetime.utcnow()
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        session_id = str(new_session.id)

    chat_messages = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )
    chat_history = utils.formatChatHistory(chat_messages.scalars().all())

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
    prompt = llm.buildPrompt(texts, q, chat_history)

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
        if not WEAK_RESPONSE_PHRASES:
            db.add(ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_text,
                created_at=datetime.utcnow()
            ))
            await db.commit()

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