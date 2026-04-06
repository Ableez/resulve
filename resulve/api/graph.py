from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from resulve.api.deps import get_session
from resulve.models import Repo
from resulve.queries import (
    BLAST_RADIUS,
    CLUSTERS,
    GRAPH_EDGES,
    GRAPH_NODES,
    NEIGHBOURHOOD,
    nodes_to_geojson,
)

router = APIRouter()


@router.get("/{repo_id}/graph")
async def get_graph(repo_id: UUID, db: AsyncSession = Depends(get_session)):
    r = await db.get(Repo, repo_id)
    if r is None:
        raise HTTPException(404, "not found")
    nodes = (await db.execute(GRAPH_NODES, {"repo_id": str(repo_id)})).mappings().all()
    edges = (await db.execute(GRAPH_EDGES, {"repo_id": str(repo_id)})).mappings().all()
    return nodes_to_geojson(nodes, edges)


@router.get("/{repo_id}/graph/neighbours")
async def neighbours(
    repo_id: UUID,
    path: str = Query(...),
    radius: float = 50.0,
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
):
    rows = await db.execute(
        NEIGHBOURHOOD,
        {"path": path, "repo_id": str(repo_id), "radius": radius, "limit": limit},
    )
    return [dict(r._mapping) for r in rows]


@router.get("/{repo_id}/graph/blast")
async def blast(
    repo_id: UUID,
    path: str = Query(...),
    max_depth: int = 3,
    db: AsyncSession = Depends(get_session),
):
    rows = await db.execute(
        BLAST_RADIUS,
        {"path": path, "repo_id": str(repo_id), "max_depth": max_depth},
    )
    return [dict(r._mapping) for r in rows]


@router.get("/{repo_id}/graph/clusters")
async def clusters(
    repo_id: UUID,
    eps: float = 30.0,
    minpoints: int = 3,
    db: AsyncSession = Depends(get_session),
):
    rows = await db.execute(
        CLUSTERS,
        {"repo_id": str(repo_id), "eps": eps, "minpoints": minpoints},
    )
    return [dict(r._mapping) for r in rows]
