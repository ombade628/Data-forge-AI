from typing import Annotated, Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.api.deps import CurrentUser, DbSession
from app.db.models import Dataset, DatasetVersion
from app.domains.quality.service import evaluate_records
from app.schemas import ColumnSpec, DatasetCreate, DatasetRead, DatasetSpecification, DatasetVersionRead

router = APIRouter(prefix="/datasets", tags=["datasets"])


async def owned_dataset(dataset_id: UUID, user: CurrentUser, db: DbSession) -> Dataset:
    dataset = await db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.owner_id == user.id))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


def validate_record(record: dict[str, Any], spec: DatasetSpecification) -> None:
    """Enforce the same shape, type, and allowed-values rules the generator applies."""
    allowed = {column.name for column in spec.columns}
    if set(record.keys()) != allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Record fields must exactly match: {', '.join(sorted(allowed))}",
        )
    columns_by_name: dict[str, ColumnSpec] = {column.name: column for column in spec.columns}
    for name, value in record.items():
        column = columns_by_name[name]
        if value is None:
            if column.required:
                raise HTTPException(status_code=422, detail=f"Field '{name}' is required")
            continue
        if column.data_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be an integer")
        if column.data_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a number")
        if column.data_type == "boolean" and not isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a boolean")
        if column.data_type == "string" and not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a string")
        if column.allowed_values and value not in column.allowed_values:
            raise HTTPException(
                status_code=422,
                detail=f"Field '{name}' must be one of: {', '.join(column.allowed_values)}",
            )


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(payload: DatasetCreate, user: CurrentUser, db: DbSession):
    dataset = Dataset(
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        specification=payload.specification.model_dump(mode="json"),
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("", response_model=list[DatasetRead])
async def list_datasets(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return (
        await db.scalars(
            select(Dataset)
            .where(Dataset.owner_id == user.id)
            .order_by(Dataset.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: UUID, user: CurrentUser, db: DbSession):
    return await owned_dataset(dataset_id, user, db)


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionRead])
async def list_versions(
    dataset_id: UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    await owned_dataset(dataset_id, user, db)
    return (
        await db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()


@router.get("/{dataset_id}/versions/{version_id}/records")
async def preview_records(
    dataset_id: UUID,
    version_id: UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    await owned_dataset(dataset_id, user, db)
    version = await db.scalar(
        select(DatasetVersion).where(
            DatasetVersion.id == version_id, DatasetVersion.dataset_id == dataset_id
        )
    )
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    return {"items": version.records[offset : offset + limit], "total": version.record_count}


@router.patch(
    "/{dataset_id}/versions/{version_id}/records/{record_index}",
    response_model=DatasetVersionRead,
)
async def edit_record(
    dataset_id: UUID,
    version_id: UUID,
    record_index: Annotated[int, Path(ge=0)],
    payload: dict[str, Any],
    user: CurrentUser,
    db: DbSession,
):
    """Edit by creating a new immutable version rather than changing historical output."""
    dataset = await owned_dataset(dataset_id, user, db)
    source = await db.scalar(
        select(DatasetVersion).where(
            DatasetVersion.id == version_id, DatasetVersion.dataset_id == dataset.id
        )
    )
    if not source or not 0 <= record_index < len(source.records):
        raise HTTPException(status_code=404, detail="Record not found")
    spec = DatasetSpecification.model_validate(source.schema_definition)
    validate_record(payload, spec)
    records = [*source.records]
    records[record_index] = payload
    quality = evaluate_records(records, spec)

    # Retry on the (dataset_id, version_number) UNIQUE constraint so concurrent
    # edits to the same dataset don't surface as 500s.
    for _ in range(3):
        latest_number = await db.scalar(
            select(func.max(DatasetVersion.version_number)).where(
                DatasetVersion.dataset_id == dataset.id
            )
        )
        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=(latest_number or 0) + 1,
            schema_definition=source.schema_definition,
            records=records,
            record_count=len(records),
            quality_report=quality,
        )
        db.add(version)
        try:
            await db.commit()
            await db.refresh(version)
            return version
        except IntegrityError:
            await db.rollback()
            continue
    raise HTTPException(
        status_code=409,
        detail="Could not allocate a new version number; retry the edit",
    )