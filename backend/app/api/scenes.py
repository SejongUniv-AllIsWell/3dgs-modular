from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import SceneOutput, Module, Floor
from app.schemas.uploads import SceneResponse, SceneDownloadResponse
from app.services.minio_service import get_minio_service

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("", response_model=list[SceneResponse])
async def list_scenes(
    building_id: Optional[UUID] = Query(None),
    floor_id: Optional[UUID] = Query(None),
    module_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """건물/층/모듈별 씬 목록 조회 (공개)"""
    query = (
        select(SceneOutput)
        .join(Module, SceneOutput.module_id == Module.id)
        .join(Floor, Module.floor_id == Floor.id)
        .where(SceneOutput.is_aligned == True)
    )

    if module_id:
        query = query.where(SceneOutput.module_id == module_id)
    elif floor_id:
        query = query.where(Module.floor_id == floor_id)
    elif building_id:
        query = query.where(Floor.building_id == building_id)

    query = query.order_by(SceneOutput.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(
    scene_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """씬 상세 조회"""
    result = await db.execute(
        select(SceneOutput).where(SceneOutput.id == scene_id)
    )
    scene = result.scalar_one_or_none()

    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="씬을 찾을 수 없습니다.")

    return scene


@router.get("/{scene_id}/download", response_model=SceneDownloadResponse)
async def download_scene(
    scene_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """SOG 파일 presigned GET URL 반환"""
    result = await db.execute(
        select(SceneOutput).where(SceneOutput.id == scene_id)
    )
    scene = result.scalar_one_or_none()

    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="씬을 찾을 수 없습니다.")

    minio = get_minio_service()

    if not minio.object_exists(scene.sog_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOG 파일을 찾을 수 없습니다.")

    expires = 3600
    url = minio.get_presigned_download_url(scene.sog_path, expires)

    return SceneDownloadResponse(url=url, expires_in=expires)
