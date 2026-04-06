from resulve.embeddings import Embedder


class FakeOpenAI:
    def __init__(self):
        self.embeddings = self
        self.calls = []

    def create(self, model, input):
        self.calls.append({"model": model, "input": list(input)})
        data = [type("E", (), {"embedding": [float(i % 7) / 10 for i in range(1536)]})() for _ in input]
        return type("R", (), {"data": data})()


def test_embed_batch_chunks_into_batch_size():
    fake = FakeOpenAI()
    e = Embedder(client=fake, model="stub", dim=1536)
    e.batch_size = 10
    texts = [f"t{i}" for i in range(25)]
    vectors = e.embed_batch(texts)
    assert len(vectors) == 25
    assert all(len(v) == 1536 for v in vectors)
    assert len(fake.calls) == 3
    assert len(fake.calls[0]["input"]) == 10
    assert len(fake.calls[2]["input"]) == 5


def test_embed_one_roundtrip():
    fake = FakeOpenAI()
    e = Embedder(client=fake, model="stub")
    v = e.embed_one("hello")
    assert len(v) == 1536


def test_embed_skips_null_chars():
    fake = FakeOpenAI()
    e = Embedder(client=fake, model="stub")
    e.embed_batch(["ok\x00bad"])
    sent = fake.calls[0]["input"][0]
    assert "\x00" not in sent


def test_embed_empty_list_returns_empty():
    fake = FakeOpenAI()
    e = Embedder(client=fake, model="stub")
    assert e.embed_batch([]) == []
    assert fake.calls == []
