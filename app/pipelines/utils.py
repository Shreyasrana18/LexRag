from sqlalchemy import select
from fastapi import UploadFile
from fastapi import APIRouter, File, UploadFile, HTTPException, Header, status
from typing import Annotated
import magic
import app.pipelines.parser as parser

MAX_SIZE = 1024 * 1024  # 1 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}


async def validateFile(
    file: UploadFile = File(...),
    content_length: Annotated[int | None, Header()] = None 
    ):
    header = await file.read(2048)
    await file.seek(0)
    if content_length and content_length > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    mime_type = magic.from_buffer(header, mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type.")
    return await file.read()

async def validateSession(db, session_id: str) -> bool:
    from app.db.models import ChatSession
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    return session is not None


def formatChatHistory(messages):
    formatted_history = []
    for msg in messages:
        formatted_history.append({
            "role": msg.role,
            "content": msg.content
        })
    return formatted_history