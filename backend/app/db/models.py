import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="owner")


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    specification: Mapped[dict] = mapped_column(JSONType, default=dict)
    owner: Mapped[User] = relationship(back_populates="datasets")
    versions: Mapped[list["DatasetVersion"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(TimestampMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_number"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    schema_definition: Mapped[dict] = mapped_column(JSONType)
    records: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    quality_report: Mapped[dict] = mapped_column(JSONType, default=dict)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    dataset: Mapped[Dataset] = relationship(back_populates="versions")


class GenerationJob(TimestampMixin, Base):
    __tablename__ = "generation_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    requested_records: Mapped[int] = mapped_column(Integer)
    generated_records: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100))
    usage: Mapped[dict] = mapped_column(JSONType, default=dict)

