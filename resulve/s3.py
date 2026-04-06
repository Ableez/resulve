import boto3
from botocore.client import Config

from resulve.config import get_settings


def make_client():
    s = get_settings()
    kwargs = {"region_name": s.s3_region, "config": Config(signature_version="s3v4")}
    if s.s3_endpoint_url:
        kwargs["endpoint_url"] = s.s3_endpoint_url
    if s.s3_access_key and s.s3_secret_key:
        kwargs["aws_access_key_id"] = s.s3_access_key
        kwargs["aws_secret_access_key"] = s.s3_secret_key
    return boto3.client("s3", **kwargs)


class S3Store:
    def __init__(self, client=None, bucket=None):
        self.client = client or make_client()
        self.bucket = bucket or get_settings().s3_bucket

    def put(self, key, body, content_type="application/octet-stream"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        return key

    def get(self, key):
        r = self.client.get_object(Bucket=self.bucket, Key=key)
        return r["Body"].read()

    def presign(self, key, expires=3600):
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

    def key_for_file(self, repo_id, commit_sha, path):
        return f"repos/{repo_id}/{commit_sha}/{path.lstrip('/')}"
