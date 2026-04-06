import hashlib
import hmac
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from resulve.api.app import create_app
from resulve.api.deps import get_embedder, get_session
from resulve.models import Repo
from tests.conftest import FakeAsyncSession, FakeResult


@pytest.fixture
def fake_session():
    return FakeAsyncSession()


@pytest.fixture
def client(fake_session, fake_embedder):
    app = create_app()

    async def _session_override():
        yield fake_session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_repo_happy_path(client, fake_session):
    body = {"name": "proj", "remote_url": "https://github.com/foo/bar.git", "default_branch": "main"}
    r = client.post("/repos", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "proj"
    assert data["status"] == "pending"
    assert len(fake_session.added) == 1


def test_create_repo_conflict_when_already_exists(client, fake_session):
    existing = Repo(
        id=uuid.uuid4(),
        name="old",
        remote_url="https://github.com/foo/bar.git",
        default_branch="main",
        status="ready",
    )
    fake_session.rows_for["remote_url"] = existing
    body = {"name": "proj", "remote_url": "https://github.com/foo/bar.git"}
    r = client.post("/repos", json=body)
    assert r.status_code == 409


def test_get_repo_not_found(client):
    r = client.get(f"/repos/{uuid.uuid4()}")
    assert r.status_code == 404


def test_get_repo_found(client, fake_session):
    rid = uuid.uuid4()
    fake_session.objects_by_id[("Repo", str(rid))] = Repo(
        id=rid, name="p", remote_url="u", default_branch="main", status="ready"
    )
    r = client.get(f"/repos/{rid}")
    assert r.status_code == 200
    assert r.json()["id"] == str(rid)


def test_kick_index_enqueues_task(client, fake_session, monkeypatch):
    rid = uuid.uuid4()
    fake_session.objects_by_id[("Repo", str(rid))] = Repo(
        id=rid, name="p", remote_url="u", default_branch="main", status="ready"
    )

    called = {}

    def fake_delay(arg):
        called["arg"] = arg
        return SimpleNamespace(id="task-xyz")

    monkeypatch.setattr(
        "resulve.api.repos.trigger_full_index",
        SimpleNamespace(delay=fake_delay),
    )

    r = client.post(f"/repos/{rid}/index")
    assert r.status_code == 202
    assert r.json()["task_id"] == "task-xyz"
    assert called["arg"] == str(rid)


def test_semantic_search_returns_rows(client, fake_session, fake_embedder):
    row = SimpleNamespace(
        id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        chunk_type="function",
        name="handle_payment",
        start_line=10,
        end_line=42,
        raw_source="def handle_payment(): pass",
        score=0.87,
    )
    fake_session.rows_for["chunk_embeddings"] = [row]
    r = client.post("/search/semantic", json={"query": "payments", "limit": 5})
    assert r.status_code == 200, r.text
    out = r.json()
    assert len(out) == 1
    assert out[0]["name"] == "handle_payment"
    assert fake_embedder.calls == ["payments"]


def test_fts_search_returns_rows(client, fake_session):
    row = SimpleNamespace(
        id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        chunk_type="function",
        name="find_user",
        start_line=1,
        end_line=5,
        raw_source="def find_user(): pass",
        score=0.12,
    )
    fake_session.rows_for["plainto_tsquery"] = [row]
    r = client.post("/search/fulltext", json={"query": "user", "limit": 3})
    assert r.status_code == 200
    assert r.json()[0]["name"] == "find_user"


def test_get_graph_returns_geojson(client, fake_session):
    rid = uuid.uuid4()
    fake_session.objects_by_id[("Repo", str(rid))] = Repo(
        id=rid, name="p", remote_url="u", default_branch="main", status="ready"
    )
    nid = uuid.uuid4()
    nodes_row = {"id": nid, "name": "svc", "module_path": "pkg/svc", "loc": 50, "x": 1.0, "y": 2.0}
    edges_row = {
        "source_module_id": nid,
        "target_module_id": nid,
        "edge_type": "import",
        "weight": 1.0,
        "sx": 0.0,
        "sy": 0.0,
        "tx": 1.0,
        "ty": 1.0,
    }
    fake_session.rows_for["FROM modules"] = [nodes_row]
    fake_session.rows_for["module_edges me"] = [edges_row]
    r = client.get(f"/repos/{rid}/graph")
    assert r.status_code == 200
    gj = r.json()
    assert gj["type"] == "FeatureCollection"
    assert any(f["geometry"]["type"] == "Point" for f in gj["features"])


def test_webhook_signature_verification(client, fake_session, monkeypatch):
    repo = Repo(id=uuid.uuid4(), name="p", remote_url="https://x/y.git", default_branch="main", status="ready")
    fake_session.rows_for["remote_url"] = repo
    body_bytes = json.dumps({"repository": {"clone_url": "https://x/y.git"}}).encode()

    sig = "sha256=" + hmac.new(b"testsecret", body_bytes, hashlib.sha256).hexdigest()

    monkeypatch.setattr(
        "resulve.api.webhooks.trigger_full_index",
        SimpleNamespace(delay=lambda rid: SimpleNamespace(id="t1")),
    )

    r = client.post(
        "/webhooks/git",
        content=body_bytes,
        headers={"X-Hub-Signature-256": sig, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["task_id"] == "t1"


def test_webhook_rejects_bad_signature(client):
    r = client.post(
        "/webhooks/git",
        content=b"{}",
        headers={"X-Hub-Signature-256": "sha256=bad", "content-type": "application/json"},
    )
    assert r.status_code == 401


def test_search_validation_rejects_empty_query(client):
    r = client.post("/search/semantic", json={"query": "", "limit": 3})
    assert r.status_code == 422
