# resulve

A self-hosted codebase cartographer. Point it at a git repo and it parses every
file, embeds every function with pgvector, builds a PostGIS spatial map of the
dependency graph, and lets you ask "what touches this API?" in plain language.

## Stack

| layer | purpose |
|---|---|
| FastAPI | async HTTP, webhook ingestion, SSE job progress |
| Celery + Redis | parse / embed / graph pipeline as a `chord` fan-out |
| Postgres 16 | one ACID store for everything |
| pgvector | HNSW index over 1536-d embeddings for semantic search |
| PostGIS | force-directed module layouts as `geometry(Point, 0)`, proximity via `ST_DWithin` |
| AWS S3 | raw file snapshots, worker artifacts, large AST blobs |

## Project layout

```
resulve/
  config.py        settings via RESULVE_* env vars
  db.py            async engine + session_scope
  models.py        SQLAlchemy (repos, files, chunks, embeddings, modules, edges, jobs)
  schemas.py       pydantic IO models
  parsing.py       ast-based chunker for python, block chunker for everything else
  graph.py         import resolution + networkx spring_layout
  embeddings.py    batched OpenAI embeddings wrapper
  s3.py            boto3 client + key layout helper
  queries.py       the three postgis patterns + geojson encoder
  worker/
    celery_app.py  Celery app + queue routing + beat schedule
    tasks.py       trigger_full_index -> chord(parse) -> finalize -> chord(embed) -> build_module_graph
  api/
    app.py         route wiring
    repos.py       repo crud + POST /repos/{id}/index
    search.py      /search/semantic, /search/fulltext
    jobs.py        /jobs/{id}, /jobs/{id}/stream (SSE)
    graph.py       /repos/{id}/graph (GeoJSON) + neighbours / blast / clusters
    webhooks.py    /webhooks/git (HMAC-verified), /webhooks/manual
  migrations/      alembic
```

## Running it

Postgres needs `pgvector`, `postgis`, and `uuid-ossp`. The simplest way:

```
docker build -t resulve/pg:16 - <<DOCK
FROM postgis/postgis:16-3.4
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-16-pgvector && rm -rf /var/lib/apt/lists/*
DOCK

docker run -d --name resulve-pg -e POSTGRES_PASSWORD=resulve -e POSTGRES_USER=resulve -e POSTGRES_DB=resulve -p 5432:5432 resulve/pg:16
docker run -d --name resulve-redis -p 6379:6379 redis:7
```

Install and migrate:

```
uv sync
uv run alembic upgrade head
```

Env vars (all optional; defaults point at localhost):

```
RESULVE_DATABASE_URL=postgresql+asyncpg://resulve:resulve@localhost:5432/resulve
RESULVE_DATABASE_URL_SYNC=postgresql+psycopg2://resulve:resulve@localhost:5432/resulve
RESULVE_REDIS_URL=redis://localhost:6379/0
RESULVE_OPENAI_API_KEY=sk-...
RESULVE_S3_BUCKET=resulve-artifacts
RESULVE_WEBHOOK_SECRET=something-long
```

Start the three processes:

```
uv run uvicorn resulve.api.app:create_app --factory --host 0.0.0.0 --port 8000
uv run celery -A resulve.worker.celery_app.celery_app worker -Q parse,embed,graph,default -l info
uv run celery -A resulve.worker.celery_app.celery_app beat -l info
```

## API examples

```
curl -X POST http://localhost:8000/repos \
  -H 'content-type: application/json' \
  -d '{"name":"myrepo","remote_url":"https://github.com/me/myrepo.git"}'

curl -X POST http://localhost:8000/repos/<id>/index

curl -N http://localhost:8000/jobs/<job_id>/stream

curl -X POST http://localhost:8000/search/semantic \
  -H 'content-type: application/json' \
  -d '{"query":"where do we charge the customer?","limit":10}'

curl "http://localhost:8000/repos/<id>/graph/neighbours?path=payments/service&radius=50"
curl "http://localhost:8000/repos/<id>/graph/blast?path=payments/service&max_depth=3"
curl "http://localhost:8000/repos/<id>/graph/clusters?eps=30&minpoints=3"
```

## Tests

```
uv run pytest
```

37 tests covering parsing, graph building, layout, the three PostGIS query
shapes, embedding batching, S3 wrapping, and all FastAPI routes with fake
session + fake embedder dependency overrides.
