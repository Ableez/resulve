from celery import Celery
from celery.schedules import crontab

from resulve.config import get_settings


def build_app():
    s = get_settings()
    app = Celery("resulve", broker=s.redis_url, backend=s.redis_url)
    app.conf.update(
        task_default_queue="default",
        task_routes={
            "resulve.worker.tasks.parse_and_chunk": {"queue": "parse"},
            "resulve.worker.tasks.embed_chunks": {"queue": "embed"},
            "resulve.worker.tasks.build_module_graph": {"queue": "graph"},
            "resulve.worker.tasks.trigger_full_index": {"queue": "default"},
            "resulve.worker.tasks.finalize_index": {"queue": "default"},
            "resulve.worker.tasks.nightly_refresh": {"queue": "default"},
        },
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        worker_prefetch_multiplier=1,
        task_track_started=True,
        beat_schedule={
            "nightly-refresh": {
                "task": "resulve.worker.tasks.nightly_refresh",
                "schedule": crontab(hour=3, minute=0),
            }
        },
    )
    return app


celery_app = build_app()
