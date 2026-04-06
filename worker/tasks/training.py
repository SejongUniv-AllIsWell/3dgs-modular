import os
import shutil
import logging
import tempfile

from celery_app import app
from minio_helper import download_file, upload_file
from redis_helper import update_progress, clear_progress

from pipeline.runner import PipelineRunner
from pipeline.ffmpeg_module import FFmpegModule
from pipeline.blur_detection import BlurDetectionModule
from pipeline.colmap_module import ColmapModule
from pipeline.gsplat_module import GsplatModule
from pipeline.sog_converter import SogConverterModule

logger = logging.getLogger(__name__)

PLY_EXT = {".ply"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _module_base(building_id: str, floor_id: str, module_id: str, module_name: str) -> str:
    return f"buildings/{building_id}/{floor_id}/modules/{module_id}_{module_name}"


@app.task(
    name="tasks.training.run_3dgs_training",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_3dgs_training(self, upload_id: str, user_id: str, minio_input_key: str,
                       building_id: str, floor_id: str, module_id: str,
                       module_name: str, ply_target: str = "gsplat"):
    """3DGS 학습 파이프라인 태스크.

    입력이 PLY인 경우:
      - ply_target="gsplat": gsplat/ 폴더에 이미 저장됨. SOG 변환만 수행.
      - ply_target="alignment": alignment/ 폴더에 저장됨 (skip_training으로 여기 도달 안 함).

    입력이 video/image인 경우:
      - 전체 파이프라인 실행 → gsplat/ 에 결과 저장.
    """
    task_id = self.request.id
    work_dir = tempfile.mkdtemp(prefix=f"3dgs_{upload_id}_")
    module_base = _module_base(building_id, floor_id, module_id, module_name)

    logger.info(f"[Task {task_id}] 3DGS 학습 시작: upload_id={upload_id}")

    try:
        ext = os.path.splitext(minio_input_key)[1].lower()
        is_ply = ext in PLY_EXT

        # 1. MinIO에서 원본 파일 다운로드
        update_progress(task_id, 0, "다운로드")
        local_input = os.path.join(work_dir, f"input{ext}")
        download_file(minio_input_key, local_input)
        logger.info(f"[Task {task_id}] 다운로드 완료: {minio_input_key}")

        if is_ply:
            # PLY 파일: SOG 변환만 수행하여 gsplat/ 에 저장
            update_progress(task_id, 50, "SOG 변환")
            sog_local = os.path.join(work_dir, f"{module_name}.sog")
            # stub: 실제 SOG 변환 시 교체
            shutil.copy2(local_input, sog_local)

            update_progress(task_id, 90, "업로드")
            ply_key = f"{module_base}/gsplat/{module_name}.ply"
            sog_key = f"{module_base}/gsplat/{module_name}.sog"
            upload_file(local_input, ply_key)
            upload_file(sog_local, sog_key)

            update_progress(task_id, 100, "완료")
            return {
                "status": "completed",
                "upload_id": upload_id,
                "ply_key": ply_key,
                "sog_key": sog_key,
            }

        # 2. 파이프라인 실행 (video / image)
        def progress_callback(progress, module_nm):
            scaled = 5 + int(progress * 0.85)
            update_progress(task_id, scaled, module_nm)

        modules = [
            FFmpegModule(fps=2),
            BlurDetectionModule(),
            ColmapModule(),
            GsplatModule(),
            SogConverterModule(),
        ]

        runner = PipelineRunner(modules)
        sog_path = runner.run(local_input, progress_callback)
        ply_path = os.path.splitext(sog_path)[0] + ".ply"

        # 3. MinIO에 결과 업로드 → gsplat/ 폴더
        update_progress(task_id, 90, "업로드")
        ply_key = f"{module_base}/gsplat/{module_name}.ply"
        sog_key = f"{module_base}/gsplat/{module_name}.sog"

        if os.path.isfile(ply_path):
            upload_file(ply_path, ply_key)
        upload_file(sog_path, sog_key)

        logger.info(f"[Task {task_id}] 결과 업로드 완료")

        update_progress(task_id, 100, "완료")

        return {
            "status": "completed",
            "upload_id": upload_id,
            "ply_key": ply_key,
            "sog_key": sog_key,
        }

    except Exception as e:
        logger.error(f"[Task {task_id}] 실패: {e}")
        update_progress(task_id, -1, f"실패: {str(e)[:200]}")
        raise

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
        clear_progress(task_id)
