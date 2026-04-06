import os
import tempfile
import uuid
from datetime import datetime, timezone
from subprocess import run, PIPE

from celery import chord, group
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from resulve.config import get_settings
from resulve.embeddings import Embedder
from resulve.graph import build_dep_graph, compute_layout, module_path_from_file
from resulve.models import (
    ChunkEmbedding,
    CodeChunk,
    IndexJob,
    Module,
    ModuleEdge,
    Repo,
    RepoFile,
)
from resulve.parsing import chunk_file, detect_language
from resulve.s3 import S3Store
from resulve.worker.celery_app import celery_app


def sync_engine():
    return create_engine(get_settings().database_url_sync, future=True)


def clone_repo(remote_url, branch, dest):
    cmd = ["git", "clone", "--depth", "1", "--branch", branch, remote_url, dest]
    r = run(cmd, stdout=PIPE, stderr=PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"git clone failed: {r.stderr.decode(errors='ignore')}")
    sha = run(["git", "-C", dest, "rev-parse", "HEAD"], stdout=PIPE).stdout.decode().strip()
    return sha


def walk_repo(root):
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            out.append((full, rel))
    return out


@celery_app.task(bind=True, name="resulve.worker.tasks.trigger_full_index")
def trigger_full_index(self, repo_id):
    eng = sync_engine()
    with Session(eng) as db:
        repo = db.get(Repo, uuid.UUID(repo_id))
        if repo is None:
            raise RuntimeError(f"repo {repo_id} not found")
        job = IndexJob(
            repo_id=repo.id,
            celery_task_id=self.request.id,
            status="running",
            progress={"phase": "clone", "files_total": 0, "files_done": 0},
        )
        db.add(job)
        repo.status = "indexing"
        db.commit()
        job_id = str(job.id)

    self.update_state(state="PROGRESS", meta={"phase": "clone"})

    with tempfile.TemporaryDirectory(prefix="resulve-") as tmp:
        sha = clone_repo(repo.remote_url, repo.default_branch, tmp)
        files = walk_repo(tmp)

        with Session(eng) as db:
            job = db.get(IndexJob, uuid.UUID(job_id))
            job.progress = {"phase": "parse", "files_total": len(files), "files_done": 0}
            db.commit()

        s3 = S3Store()
        file_refs = []
        for full, rel in files:
            try:
                with open(full, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            if len(raw) > 2_000_000:
                continue
            try:
                text_src = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            key = s3.key_for_file(repo_id, sha, rel)
            try:
                s3.put(key, text_src, content_type="text/plain")
            except Exception:
                pass
            file_refs.append({"path": rel, "s3_key": key, "commit_sha": sha, "source": text_src})

        with Session(eng) as db:
            db.execute(text("DELETE FROM repo_files WHERE repo_id = :r"), {"r": repo_id})
            persisted = []
            for ref in file_refs:
                rf = RepoFile(
                    repo_id=uuid.UUID(repo_id),
                    s3_key=ref["s3_key"],
                    path=ref["path"],
                    language=detect_language(ref["path"]),
                    commit_sha=ref["commit_sha"],
                )
                db.add(rf)
                db.flush()
                persisted.append((rf.id, ref))
            db.commit()

        parse_sigs = [
            parse_and_chunk.s(str(fid), ref["path"], ref["source"])
            for fid, ref in persisted
        ]
        callback = finalize_index.s(repo_id=repo_id, job_id=job_id)
        if parse_sigs:
            chord(parse_sigs)(callback)
        else:
            finalize_index.delay([], repo_id=repo_id, job_id=job_id)

    return {"job_id": job_id, "files": len(file_refs)}


@celery_app.task(name="resulve.worker.tasks.parse_and_chunk")
def parse_and_chunk(file_id, path, source):
    chunks = chunk_file(path, source)
    eng = sync_engine()
    with Session(eng) as db:
        chunk_ids = []
        for ch in chunks:
            row = CodeChunk(
                file_id=uuid.UUID(file_id),
                chunk_type=ch["chunk_type"],
                name=ch["name"],
                start_line=ch["start_line"],
                end_line=ch["end_line"],
                raw_source=ch["raw_source"],
            )
            db.add(row)
            db.flush()
            chunk_ids.append(str(row.id))
        db.execute(
            text(
                "UPDATE code_chunks SET fts_vector = to_tsvector('english', coalesce(name,'') || ' ' || coalesce(raw_source,'')) WHERE file_id = :f"
            ),
            {"f": file_id},
        )
        db.commit()
    return {"file_id": file_id, "path": path, "chunk_ids": chunk_ids, "chunks": chunks}


@celery_app.task(name="resulve.worker.tasks.finalize_index")
def finalize_index(parse_results, repo_id, job_id):
    eng = sync_engine()
    all_chunk_ids = []
    files_payload = []
    for r in parse_results:
        all_chunk_ids.extend(r["chunk_ids"])
        files_payload.append({"path": r["path"], "chunks": r["chunks"]})

    with Session(eng) as db:
        job = db.get(IndexJob, uuid.UUID(job_id))
        job.progress = {
            "phase": "embed",
            "files_total": len(files_payload),
            "files_done": len(files_payload),
            "chunks_total": len(all_chunk_ids),
        }
        db.commit()

    batch_size = get_settings().embedding_batch_size
    embed_sigs = []
    for i in range(0, len(all_chunk_ids), batch_size):
        embed_sigs.append(embed_chunks.s(all_chunk_ids[i : i + batch_size]))

    graph_sig = build_module_graph.s(repo_id=repo_id, files=files_payload, job_id=job_id)

    if embed_sigs:
        chord(embed_sigs)(graph_sig)
    else:
        graph_sig.delay()
    return {"job_id": job_id, "chunks": len(all_chunk_ids)}


@celery_app.task(name="resulve.worker.tasks.embed_chunks")
def embed_chunks(chunk_ids):
    if not chunk_ids:
        return {"count": 0}
    eng = sync_engine()
    s = get_settings()
    embedder = Embedder()
    with Session(eng) as db:
        db.execute(text("SET LOCAL hnsw.ef_search = :v"), {"v": s.bulk_hnsw_ef})
        rows = db.execute(
            select(CodeChunk).where(CodeChunk.id.in_([uuid.UUID(i) for i in chunk_ids]))
        ).scalars().all()
        texts = [f"{r.name}\n{r.raw_source}" for r in rows]
        vectors = embedder.embed_batch(texts)
        to_insert = []
        for r, v in zip(rows, vectors):
            to_insert.append({
                "id": uuid.uuid4(),
                "chunk_id": r.id,
                "embedding": v,
                "model_version": s.embedding_model,
            })
        if to_insert:
            stmt = pg_insert(ChunkEmbedding).values(to_insert)
            stmt = stmt.on_conflict_do_update(
                index_elements=["chunk_id", "model_version"],
                set_={"embedding": stmt.excluded.embedding},
            )
            db.execute(stmt)
        db.commit()
    return {"count": len(chunk_ids)}


@celery_app.task(name="resulve.worker.tasks.build_module_graph")
def build_module_graph(_prev, repo_id, files, job_id):
    nodes, edges, locs = build_dep_graph(files)
    layout = compute_layout(nodes, edges)
    eng = sync_engine()
    with Session(eng) as db:
        db.execute(text("DELETE FROM module_edges WHERE source_module_id IN (SELECT id FROM modules WHERE repo_id = :r)"), {"r": repo_id})
        db.execute(text("DELETE FROM modules WHERE repo_id = :r"), {"r": repo_id})
        name_to_id = {}
        for n in nodes:
            x, y = layout.get(n, (0.0, 0.0))
            row = db.execute(
                text(
                    "INSERT INTO modules (id, repo_id, name, module_path, spatial_coord, loc) "
                    "VALUES (:id, :r, :n, :p, ST_SetSRID(ST_MakePoint(:x, :y), 0), :loc) RETURNING id"
                ),
                {
                    "id": uuid.uuid4(),
                    "r": repo_id,
                    "n": n.rsplit("/", 1)[-1],
                    "p": n,
                    "x": x,
                    "y": y,
                    "loc": locs.get(n, 0),
                },
            ).fetchone()
            name_to_id[n] = row[0]
        for src, dst, w in edges:
            if src in name_to_id and dst in name_to_id:
                db.execute(
                    text(
                        "INSERT INTO module_edges (id, source_module_id, target_module_id, edge_type, weight) "
                        "VALUES (:id, :s, :t, :e, :w)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "s": name_to_id[src],
                        "t": name_to_id[dst],
                        "e": "import",
                        "w": w,
                    },
                )
        job = db.get(IndexJob, uuid.UUID(job_id))
        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        job.progress = {"phase": "done", "modules": len(nodes), "edges": len(edges)}
        repo = db.get(Repo, uuid.UUID(repo_id))
        repo.status = "ready"
        repo.last_indexed_at = datetime.now(timezone.utc)
        db.commit()
    return {"modules": len(nodes), "edges": len(edges)}


@celery_app.task(name="resulve.worker.tasks.nightly_refresh")
def nightly_refresh():
    eng = sync_engine()
    with Session(eng) as db:
        repos = db.execute(select(Repo)).scalars().all()
        ids = [str(r.id) for r in repos]
    for rid in ids:
        trigger_full_index.delay(rid)
    return {"scheduled": len(ids)}
