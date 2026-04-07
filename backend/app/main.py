from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware import AccessLogMiddleware
from app.api.auth import router as auth_router
from app.api.uploads import router as uploads_router
from app.api.scenes import router as scenes_router
from app.api.tasks import router as tasks_router
from app.api.ws import router as ws_router
from app.api.notifications import router as notifications_router
from app.api.basemaps import router as basemaps_router
from app.api.buildings import router as buildings_router
from app.api.refine import router as refine_router


from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 초기화
    yield
    # 종료 시 정리


app = FastAPI(
    title="3DGS Platform API",
    root_path="/api",
    lifespan=lifespan,
)

# CORS
cors_origins = ["*"]
if settings.PUBLIC_BASE_URL:
    cors_origins = [
        settings.PUBLIC_BASE_URL,
        "http://localhost",
        "http://192.168.0.51",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 액세스 로그
app.add_middleware(AccessLogMiddleware)

# 라우터 등록
app.include_router(auth_router)
app.include_router(uploads_router)
app.include_router(scenes_router)
app.include_router(tasks_router)
app.include_router(ws_router)
app.include_router(notifications_router)
app.include_router(basemaps_router)
app.include_router(buildings_router)
app.include_router(refine_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
