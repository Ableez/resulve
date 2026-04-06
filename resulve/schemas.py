from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class RepoIn(BaseModel):
    name: str
    remote_url: str
    default_branch: str = "main"


class RepoOut(BaseModel):
    id: UUID
    name: str
    remote_url: str
    default_branch: str
    status: str
    last_indexed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChunkOut(BaseModel):
    id: UUID
    file_id: UUID
    chunk_type: str
    name: str
    start_line: int
    end_line: int
    raw_source: str
    score: float | None = None

    model_config = {"from_attributes": True}


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    repo_id: UUID | None = None
    limit: int = 20


class JobOut(BaseModel):
    id: UUID
    repo_id: UUID
    status: str
    progress: dict
    celery_task_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    repo_url: str
    branch: str = "main"
    commit_sha: str | None = None
