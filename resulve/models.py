import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from geoalchemy2 import Geometry

from resulve.db import Base


def uid():
    return uuid.uuid4()


class Repo(Base):
    __tablename__ = "repos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    name = Column(Text, nullable=False)
    remote_url = Column(Text, nullable=False, unique=True)
    default_branch = Column(Text, nullable=False, default="main")
    last_indexed_at = Column(DateTime(timezone=True))
    status = Column(Text, nullable=False, default="pending")

    files = relationship("RepoFile", back_populates="repo", cascade="all, delete-orphan")
    modules = relationship("Module", back_populates="repo", cascade="all, delete-orphan")
    jobs = relationship("IndexJob", back_populates="repo", cascade="all, delete-orphan")


class RepoFile(Base):
    __tablename__ = "repo_files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    s3_key = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    language = Column(Text, nullable=False, default="text")
    commit_sha = Column(Text, nullable=False)
    indexed_at = Column(DateTime(timezone=True), server_default=func.now())

    repo = relationship("Repo", back_populates="files")
    chunks = relationship("CodeChunk", back_populates="file", cascade="all, delete-orphan")


class CodeChunk(Base):
    __tablename__ = "code_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    file_id = Column(UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="CASCADE"), nullable=False)
    chunk_type = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    raw_source = Column(Text, nullable=False)
    fts_vector = Column(TSVECTOR)

    file = relationship("RepoFile", back_populates="chunks")
    embeddings = relationship("ChunkEmbedding", back_populates="chunk", cascade="all, delete-orphan")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("code_chunks.id", ondelete="CASCADE"), nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    model_version = Column(Text, nullable=False)

    chunk = relationship("CodeChunk", back_populates="embeddings")


class Module(Base):
    __tablename__ = "modules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    module_path = Column(Text, nullable=False)
    spatial_coord = Column(Geometry(geometry_type="POINT", srid=0), nullable=False)
    loc = Column(Integer, nullable=False, default=0)

    repo = relationship("Repo", back_populates="modules")


class ModuleEdge(Base):
    __tablename__ = "module_edges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    source_module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False)
    target_module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False)
    edge_type = Column(Text, nullable=False, default="import")
    weight = Column(Float, nullable=False, default=1.0)


class IndexJob(Base):
    __tablename__ = "index_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    celery_task_id = Column(Text)
    status = Column(Text, nullable=False, default="pending")
    progress = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

    repo = relationship("Repo", back_populates="jobs")
