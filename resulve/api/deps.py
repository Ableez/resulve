from resulve.db import get_session
from resulve.embeddings import Embedder


_embedder = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def set_embedder(e):
    global _embedder
    _embedder = e


__all__ = ["get_session", "get_embedder", "set_embedder"]
