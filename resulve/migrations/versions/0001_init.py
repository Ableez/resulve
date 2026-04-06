"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from pgvector.sqlalchemy import Vector
from geoalchemy2 import Geometry


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    op.create_table(
        "repos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("remote_url", sa.Text, nullable=False, unique=True),
        sa.Column("default_branch", sa.Text, nullable=False, server_default="main"),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
    )

    op.create_table(
        "repo_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", UUID(as_uuid=True), sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("s3_key", sa.Text, nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("language", sa.Text, nullable=False, server_default="text"),
        sa.Column("commit_sha", sa.Text, nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_repo_files_repo_id", "repo_files", ["repo_id"])
    op.create_index("ix_repo_files_path", "repo_files", ["repo_id", "path"])

    op.create_table(
        "code_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", UUID(as_uuid=True), sa.ForeignKey("repo_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_type", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("start_line", sa.Integer, nullable=False),
        sa.Column("end_line", sa.Integer, nullable=False),
        sa.Column("raw_source", sa.Text, nullable=False),
        sa.Column("fts_vector", TSVECTOR),
    )
    op.create_index("ix_code_chunks_file_id", "code_chunks", ["file_id"])
    op.execute("CREATE INDEX ix_code_chunks_fts ON code_chunks USING GIN (fts_vector)")

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("code_chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.UniqueConstraint("chunk_id", "model_version", name="uq_chunk_model"),
    )

    op.create_table(
        "modules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", UUID(as_uuid=True), sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("module_path", sa.Text, nullable=False),
        sa.Column("spatial_coord", Geometry(geometry_type="POINT", srid=0), nullable=False),
        sa.Column("loc", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_modules_repo_path", "modules", ["repo_id", "module_path"], unique=True)

    op.create_table(
        "module_edges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_module_id", UUID(as_uuid=True), sa.ForeignKey("modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_module_id", UUID(as_uuid=True), sa.ForeignKey("modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_type", sa.Text, nullable=False, server_default="import"),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
    )
    op.create_index("ix_edges_source", "module_edges", ["source_module_id"])
    op.create_index("ix_edges_target", "module_edges", ["target_module_id"])

    op.create_table(
        "index_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_id", UUID(as_uuid=True), sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("celery_task_id", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("progress", JSONB, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_jobs_repo", "index_jobs", ["repo_id"])

    op.execute(
        "CREATE INDEX ix_chunk_embeddings_hnsw ON chunk_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw")
    op.drop_table("index_jobs")
    op.drop_table("module_edges")
    op.drop_table("modules")
    op.drop_table("chunk_embeddings")
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_fts")
    op.drop_table("code_chunks")
    op.drop_table("repo_files")
    op.drop_table("repos")
