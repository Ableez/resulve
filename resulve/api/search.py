from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from resulve.api.deps import get_embedder, get_session
from resulve.config import get_settings
from resulve.embeddings import Embedder
from resulve.queries import FTS_SEARCH, SEMANTIC_SEARCH
from resulve.schemas import ChunkOut, SearchIn

router = APIRouter()


def _row_to_chunk(row):
    return ChunkOut(
        id=row.id,
        file_id=row.file_id,
        chunk_type=row.chunk_type,
        name=row.name,
        start_line=row.start_line,
        end_line=row.end_line,
        raw_source=row.raw_source,
        score=float(row.score) if row.score is not None else None,
    )


@router.post("/semantic", response_model=list[ChunkOut])
async def semantic_search(
    body: SearchIn,
    db: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
):
    vec = embedder.embed_one(body.query)
    s = get_settings()
    await db.execute(
        __import__("sqlalchemy").text("SET LOCAL hnsw.ef_search = :v"), {"v": s.query_hnsw_ef}
    )
    result = await db.execute(
        SEMANTIC_SEARCH,
        {
            "vec": vec,
            "model": s.embedding_model,
            "repo_id": str(body.repo_id) if body.repo_id else None,
            "limit": body.limit,
        },
    )
    return [_row_to_chunk(r) for r in result]


@router.post("/fulltext", response_model=list[ChunkOut])
async def fts_search(body: SearchIn, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        FTS_SEARCH,
        {
            "q": body.query,
            "repo_id": str(body.repo_id) if body.repo_id else None,
            "limit": body.limit,
        },
    )
    return [_row_to_chunk(r) for r in result]
