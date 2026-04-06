from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from resulve.api.deps import get_session
from resulve.models import Repo
from resulve.schemas import RepoIn, RepoOut
from resulve.worker.tasks import trigger_full_index

router = APIRouter()


@router.post("", response_model=RepoOut, status_code=201)
async def create_repo(body: RepoIn, db: AsyncSession = Depends(get_session)):
    existing = (await db.execute(select(Repo).where(Repo.remote_url == body.remote_url))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "repo already exists")
    r = Repo(name=body.name, remote_url=body.remote_url, default_branch=body.default_branch, status="pending")
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return RepoOut.model_validate(r)


@router.get("", response_model=list[RepoOut])
async def list_repos(db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Repo).order_by(Repo.name))).scalars().all()
    return [RepoOut.model_validate(r) for r in rows]


@router.get("/{repo_id}", response_model=RepoOut)
async def get_repo(repo_id: UUID, db: AsyncSession = Depends(get_session)):
    r = await db.get(Repo, repo_id)
    if r is None:
        raise HTTPException(404, "not found")
    return RepoOut.model_validate(r)


@router.post("/{repo_id}/index", status_code=202)
async def kick_index(repo_id: UUID, db: AsyncSession = Depends(get_session)):
    r = await db.get(Repo, repo_id)
    if r is None:
        raise HTTPException(404, "not found")
    task = trigger_full_index.delay(str(repo_id))
    return {"task_id": task.id, "repo_id": str(repo_id)}
