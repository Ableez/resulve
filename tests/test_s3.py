from io import BytesIO
from unittest.mock import MagicMock

from resulve.s3 import S3Store


def test_put_encodes_strings():
    client = MagicMock()
    store = S3Store(client=client, bucket="b")
    store.put("k", "hello")
    args, kwargs = client.put_object.call_args
    assert kwargs["Bucket"] == "b"
    assert kwargs["Key"] == "k"
    assert kwargs["Body"] == b"hello"


def test_get_reads_body():
    client = MagicMock()
    client.get_object.return_value = {"Body": BytesIO(b"data")}
    store = S3Store(client=client, bucket="b")
    assert store.get("k") == b"data"


def test_presign_delegates():
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://x"
    store = S3Store(client=client, bucket="b")
    url = store.presign("k", expires=42)
    assert url == "https://x"
    client.generate_presigned_url.assert_called_once()


def test_key_for_file_layout():
    client = MagicMock()
    store = S3Store(client=client, bucket="b")
    k = store.key_for_file("r1", "sha1", "/app/main.py")
    assert k == "repos/r1/sha1/app/main.py"
