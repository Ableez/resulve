import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from resulve.api.deps import get_session
from resulve.models import IndexJob
from resulve.schemas import JobOut

router = APIRouter()


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_session)):
    j = await db.get(IndexJob, job_id)
    if j is None:
        raise HTTPException(404, "not found")
    return JobOut.model_validate(j)


async def _iter_progress(job_id):
    from resulve.db import session_scope
    last = None
    for _ in range(600):
        async with session_scope() as db:
            j = await db.get(IndexJob, job_id)
            if j is None:
                yield "event: error\ndata: {}\n\n"
                return
            payload = {
                "status": j.status,
                "progress": j.progress or {},
            }
        body = json.dumps(payload)
        if body != last:
            yield f"event: progress\ndata: {body}\n\n"
            last = body
        if payload["status"] in ("done", "failed"):
            return
        await asyncio.sleep(0.5)


@router.get("/{job_id}/stream")
async def stream_job(job_id: UUID):
    return StreamingResponse(_iter_progress(job_id), media_type="text/event-stream")
