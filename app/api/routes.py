from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import app.pipelines.utils as utils
import app.services.core as core
from app.db.postgres import db
from app.db.models import Case
import uuid
from uuid import UUID

router = APIRouter()

@router.post("/upload", tags=["upload"])
async def upload(
    validated_bytes: bytes = Depends(utils.validateFile),
    db: AsyncSession = Depends(db)
):
    return await core.processUpload(validated_bytes, db)


@router.get("/search", tags=["search"])
async def search(
    db: AsyncSession = Depends(db),
    q: str = Query(min_length=2),
    case_id: str | None = Query(None),
    stream: bool = False,
    session_id: str | None = Query(None)
):
    if session_id:
        isValidSession = await utils.validateSession(db, session_id)
        if session_id and not isValidSession:
            return {"error": "Invalid session_id"}
    return await core.search(db, q, stream, case_id, session_id)



@router.get("/cases/{case_id}/status", tags=["cases"])
async def get_case_status(
    case_id: UUID,
    db: AsyncSession = Depends(db)
):
    case = await db.get(Case, case_id)

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )
    return {
        "case_id": str(case_id),
        "status": case.status
    }