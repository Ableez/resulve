import os
import sys
import uuid
from types import SimpleNamespace

import pytest

os.environ.setdefault("RESULVE_OPENAI_API_KEY", "test")
os.environ.setdefault("RESULVE_WEBHOOK_SECRET", "testsecret")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self._rows)


class FakeAsyncSession:
    def __init__(self, rows_for=None, objects_by_id=None):
        self.rows_for = rows_for or {}
        self.objects_by_id = objects_by_id or {}
        self.added = []
        self.executed = []

    async def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        key = str(stmt)
        for k, v in self.rows_for.items():
            if k in key:
                return FakeResult(rows=v) if isinstance(v, list) else FakeResult(scalar=v)
        return FakeResult(rows=[])

    async def get(self, cls, pk):
        return self.objects_by_id.get((cls.__name__, str(pk)))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def rollback(self):
        pass


@pytest.fixture
def fake_session_factory():
    def _make(**kwargs):
        return FakeAsyncSession(**kwargs)
    return _make


@pytest.fixture
def fake_embedder():
    class FakeEmbedder:
        def __init__(self):
            self.calls = []
            self.dim = 1536

        def embed_one(self, text):
            self.calls.append(text)
            return [0.01] * self.dim

        def embed_batch(self, texts):
            for t in texts:
                self.calls.append(t)
            return [[0.01] * self.dim for _ in texts]

    return FakeEmbedder()
