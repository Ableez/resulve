from resulve.config import get_settings


class Embedder:
    def __init__(self, client=None, model=None, dim=None):
        s = get_settings()
        self.model = model or s.embedding_model
        self.dim = dim or s.embedding_dim
        self.batch_size = s.embedding_batch_size
        self._client = client

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=get_settings().openai_api_key)
        return self._client

    def embed_one(self, text):
        return self.embed_batch([text])[0]

    def embed_batch(self, texts):
        if not texts:
            return []
        out = []
        c = self._get_client()
        for i in range(0, len(texts), self.batch_size):
            window = texts[i : i + self.batch_size]
            cleaned = [t.replace("\x00", "") or " " for t in window]
            resp = c.embeddings.create(model=self.model, input=cleaned)
            for item in resp.data:
                out.append(list(item.embedding))
        return out
