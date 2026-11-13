"""initial dataforge schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(30), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), *timestamps(), sa.UniqueConstraint("email"))
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table("datasets", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text()), sa.Column("status", sa.String(30), nullable=False), sa.Column("specification", sa.JSON(), nullable=False), *timestamps())
    op.create_index("ix_datasets_owner_id", "datasets", ["owner_id"])
    op.create_table("dataset_versions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False), sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("schema_definition", sa.JSON(), nullable=False), sa.Column("records", sa.JSON(), nullable=False), sa.Column("quality_report", sa.JSON(), nullable=False), sa.Column("record_count", sa.Integer(), nullable=False), *timestamps(), sa.UniqueConstraint("dataset_id", "version_number"))
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])
    op.create_table("generation_jobs", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False), sa.Column("requested_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("requested_records", sa.Integer(), nullable=False), sa.Column("generated_records", sa.Integer(), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("model_name", sa.String(100), nullable=False), sa.Column("usage", sa.JSON(), nullable=False), *timestamps())
    op.create_index("ix_generation_jobs_dataset_id", "generation_jobs", ["dataset_id"])


def downgrade() -> None:
    op.drop_table("generation_jobs")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("users")

