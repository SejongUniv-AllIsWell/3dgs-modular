from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# 백엔드에서 태스크를 발행하기 위한 Celery 클라이언트
celery_app = Celery("worker")
celery_app.config_from_object({
    "broker_url": settings.RABBITMQ_URL,
    "result_backend": settings.REDIS_URL,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
})


def dispatch_training_task(
    upload_id: str,
    user_id: str,
    minio_input_key: str,
    building_id: str,
    floor_id: str,
    module_id: str,
    module_name: str,
    ply_target: str = "gsplat",
) -> str:
    """3DGS 학습 태스크 발행 → celery_task_id 반환"""
    result = celery_app.send_task(
        "tasks.training.run_3dgs_training",
        args=[
            upload_id, user_id, minio_input_key,
            building_id, floor_id, module_id, module_name, ply_target,
        ],
        queue="training",
    )
    return result.id


