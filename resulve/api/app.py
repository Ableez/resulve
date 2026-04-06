from fastapi import FastAPI

from resulve.api import graph as graph_routes
from resulve.api import jobs as job_routes
from resulve.api import repos as repo_routes
from resulve.api import search as search_routes
from resulve.api import webhooks as webhook_routes


def create_app():
    app = FastAPI(title="resulve", version="0.1.0")
    app.include_router(repo_routes.router, prefix="/repos", tags=["repos"])
    app.include_router(search_routes.router, prefix="/search", tags=["search"])
    app.include_router(job_routes.router, prefix="/jobs", tags=["jobs"])
    app.include_router(graph_routes.router, prefix="/repos", tags=["graph"])
    app.include_router(webhook_routes.router, prefix="/webhooks", tags=["webhooks"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
