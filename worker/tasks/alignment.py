import os
import json
import shutil
import logging
import tempfile

from celery_app import app
from minio_helper import download_file, upload_file
from redis_helper import update_progress, clear_progress

logger = logging.getLogger(__name__)


def _module_base(building_id: str, floor_id: str, module_id: str, module_name: str) -> str:
    return f"buildings/{building_id}/{floor_id}/modules/{module_id}_{module_name}"


@app.task(
    name="tasks.alignment.run_door_alignment",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_door_alignment(self, upload_id: str, user_id: str,
                        ply_key: str, door_position_key: str,
                        basemap_key: str, building_id: str, floor_id: str,
                        module_id: str, module_name: str):
    """문 기반 정합 태스크.

    1. MinIO에서 ply + door_position.json + basemap.ply 다운로드
    2. basemap 좌표계 기준으로 회전/이동/스케일링
    3. 정합된 결과를 alignment/ 에, 웹 출력을 web_output/ 에 저장
    """
    task_id = self.request.id
    work_dir = tempfile.mkdtemp(prefix=f"align_{upload_id}_")
    module_base = _module_base(building_id, floor_id, module_id, module_name)

    logger.info(f"[Task {task_id}] 정합 시작: upload_id={upload_id}")

    try:
        # 1. 다운로드
        update_progress(task_id, 10, "다운로드")
        local_ply = os.path.join(work_dir, "input.ply")
        local_door = os.path.join(work_dir, "door_position.json")
        local_basemap = os.path.join(work_dir, "basemap.ply")

        download_file(ply_key, local_ply)
        download_file(door_position_key, local_door)
        download_file(basemap_key, local_basemap)

        # 2. 문 위치 정보 로드
        update_progress(task_id, 30, "정합 계산")
        with open(local_door, "r") as f:
            door_position = json.load(f)

        # 3. 정합 처리
        aligned_ply = os.path.join(work_dir, "aligned.ply")
        aligned_sog = os.path.join(work_dir, "aligned.sog")

        try:
            _align_module(local_ply, local_basemap, door_position, aligned_ply)
        except Exception:
            logger.warning(f"[Task {task_id}] 정합 알고리즘 미구현. stub 복사합니다.")
            shutil.copy2(local_ply, aligned_ply)

        # SOG 변환 (stub)
        update_progress(task_id, 60, "SOG 변환")
        shutil.copy2(aligned_ply, aligned_sog)

        # 4. alignment/ 에 업로드
        update_progress(task_id, 80, "업로드")
        output_ply_key = f"{module_base}/alignment/{module_name}.ply"
        output_sog_key = f"{module_base}/alignment/{module_name}.sog"
        metadata_key = f"{module_base}/alignment/metadata.json"

        upload_file(aligned_ply, output_ply_key)
        upload_file(aligned_sog, output_sog_key)

        metadata = {
            "upload_id": upload_id,
            "user_id": user_id,
            "building_id": building_id,
            "floor_id": floor_id,
            "module_id": module_id,
            "module_name": module_name,
            "door_position": door_position,
        }
        metadata_path = os.path.join(work_dir, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        upload_file(metadata_path, metadata_key, content_type="application/json")

        # 5. web_output/ 에도 복사 (웹 뷰어용)
        web_sog_key = f"{module_base}/web_output/{module_name}.sog"
        upload_file(aligned_sog, web_sog_key)

        update_progress(task_id, 100, "완료")

        return {
            "status": "completed",
            "upload_id": upload_id,
            "ply_key": output_ply_key,
            "sog_key": output_sog_key,
            "web_sog_key": web_sog_key,
            "metadata_key": metadata_key,
        }

    except Exception as e:
        logger.error(f"[Task {task_id}] 정합 실패: {e}")
        update_progress(task_id, -1, f"실패: {str(e)[:200]}")
        raise

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
        clear_progress(task_id)


def _align_module(ply_path: str, basemap_path: str,
                   door_position: dict, output_path: str):
    """정합 알고리즘 (실제 구현 시 교체)"""
    # TODO: 실제 정합 알고리즘 구현
    shutil.copy2(ply_path, output_path)
