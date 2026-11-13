from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.api.deps import CurrentUser, DbSession
from app.db.models import Dataset, DatasetVersion
from app.services.exports import build_export

router = APIRouter(tags=["exports"])


@router.get("/dataset-versions/{version_id}/export")
async def export_version(
    version_id: UUID,
    user: CurrentUser,
    db: DbSession,
    format: str = Query("csv"),
):
    version = await db.scalar(
        select(DatasetVersion)
        .join(Dataset)
        .where(DatasetVersion.id == version_id, Dataset.owner_id == user.id)
    )
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    try:
        stream, media_type, filename = build_export(
            version.version_number, version.records, format
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return StreamingResponse(
        stream,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )