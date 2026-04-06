import hashlib
import hmac
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from resulve.api.deps import get_session
from resulve.config import get_settings
from resulve.models import Repo
from resulve.schemas import WebhookPayload
from resulve.worker.tasks import trigger_full_index

router = APIRouter()


def verify_signature(body, signature):
    secret = get_settings().webhook_secret.encode()
    digest = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature or "")


@router.post("/git")
async def git_push(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
):
    raw = await request.body()
    if not verify_signature(raw, x_hub_signature_256):
        raise HTTPException(401, "bad signature")
    data = await request.json()
    url = data.get("repository", {}).get("clone_url") or data.get("repo_url")
    if not url:
        raise HTTPException(400, "missing repo url")
    repo = (await db.execute(select(Repo).where(Repo.remote_url == url))).scalar_one_or_none()
    if repo is None:
        raise HTTPException(404, "repo not registered")
    task = trigger_full_index.delay(str(repo.id))
    return {"task_id": task.id}


@router.post("/manual")
async def manual_trigger(body: WebhookPayload, db: AsyncSession = Depends(get_session)):
    repo = (await db.execute(select(Repo).where(Repo.remote_url == body.repo_url))).scalar_one_or_none()
    if repo is None:
        raise HTTPException(404, "repo not registered")
    task = trigger_full_index.delay(str(repo.id))
    return {"task_id": task.id}
