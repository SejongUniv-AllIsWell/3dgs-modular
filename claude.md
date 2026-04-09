# CLAUDE.md — 3DGS Digital Twin Platform

## Overview

A web platform that creates digital twins of building interiors using 3D Gaussian Splatting.
Video upload → GPU server 3DGS training → door-based alignment → web viewer serving.
## Web page
https://splat.wiki/

## Tech Stack

| Role | Technology |
|------|-----------|
| Frontend | Next.js (App Router, TypeScript, Tailwind) |
| Backend | FastAPI + SQLAlchemy (async) + Alembic |
| Database | PostgreSQL |
| Cache | Redis |
| Storage | MinIO (S3-compatible object storage) |
| Queue | RabbitMQ (Celery broker) |
| GPU Worker | Celery (separate physical machine) |
| 3DGS Viewer | PlayCanvas Engine (SOG format) |
| Map | KakaoMap API |
| Auth | Google OAuth 2.0 + JWT |
| Proxy | Nginx |

## Deployment

```
[PC] docker compose
├── nginx        :80/443
├── frontend     :3000
├── backend      :8000
├── postgres     :5432
├── redis        :6379
├── rabbitmq     :5672
├── minio        :9000
└── flower       :5555

[GPU Server] separate machine
└── celery worker  ← connects to PC's RabbitMQ/Redis/MinIO over network
```

## Directory Structure

```
/
├── frontend/           # Next.js
│   ├── src/app/        # Page routing
│   ├── src/components/ # viewer/, map/, upload/, dashboard/
│   ├── src/lib/        # API client, WebSocket, utilities
│   └── src/types/
├── backend/            # FastAPI
│   ├── app/main.py
│   ├── app/core/       # config, security, database
│   ├── app/api/        # auth, uploads, tasks, scenes, basemaps, ws
│   ├── app/models/     # SQLAlchemy ORM
│   ├── app/schemas/    # Pydantic
│   ├── app/services/   # minio_service, celery_service, notification_service
│   ├── app/middleware/  # access_log
│   └── alembic/
├── worker/             # Celery (deployed on GPU server)
│   ├── tasks/          # training.py, alignment.py
│   ├── pipeline/       # base.py, ffmpeg, blur_detection, colmap, gsplat, sog_converter, runner
│   └── celery_app.py
├── nginx/nginx.conf
├── docker-compose.yml
└── .env
```

## Core Rules

### Pipeline Modules
- All modules MUST inherit `PipelineModule(ABC)` with `run(input_path) → output_path` interface
- Inter-module communication via file paths (directories) ONLY. No direct imports between modules
- Replacing any module MUST NOT affect adjacent modules
- Pipeline: FFmpeg → BlurDetection → COLMAP → gsplat → SOG conversion

### PlayCanvas Viewer
- Single component, branched by `mode` prop (edit / readonly)
- Edit mode: SOG rendering + door position selection UI
- Readonly mode: SOG rendering + camera controls only

### Authentication
- Google OAuth → JWT (Access 30min / Refresh 7days)
- Admin: `users.role = 'admin'` → basemap approval/modification privileges

### MinIO Object Keys
- `users/{user_id}/{building_name}/web_input/` — raw uploads (private)
- `users/{user_id}/{building_name}/3dgs_output/` — training results (private)
- `buildings/{building_name}/{floor}/ply|sog|metadata/` — aligned outputs (public)
- Upload: Multipart + presigned PUT URL (client uploads directly to MinIO)
- Download: presigned GET URL

### Basemap
- Initially created by admin, fundamentally immutable
- On change: compute transform matrix → apply to all existing aligned modules

### Notifications
- User online: WebSocket push (Redis `ws:online:{user_id}`)
- User offline: save to PostgreSQL `notifications` → deliver on next login

### Networking
- Inter-container communication: use docker service names (`postgres`, `redis`, etc.)
- GPU server: connects to PC via `PC_HOST_IP` environment variable
- External exposure: Nginx 80/443 only. RabbitMQ/Redis/MinIO allow GPU server IP only

## DB Tables

users, access_logs, sessions, uploads, tasks, scene_outputs, basemaps, notifications
→ See `db_schema.md` for full schema

## Environment Variables

```env
# docker compose (.env)
POSTGRES_USER=3dgs
POSTGRES_PASSWORD=changeme
POSTGRES_DB=3dgs_platform
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672//
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=changeme
MINIO_BUCKET=3dgs-platform
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
NEXT_PUBLIC_API_URL=/api
NEXT_PUBLIC_KAKAO_MAP_KEY=...

# GPU Worker (.env — uses PC's external IP)
# RABBITMQ_URL=amqp://guest:guest@<PC_IP>:5672//
# REDIS_URL=redis://<PC_IP>:6379/0
# MINIO_ENDPOINT=<PC_IP>:9000
```

## Pages

| Path | Description | Auth |
|------|-------------|------|
| `/` | Landing page | None |
| `/login` | Google login | None |
| `/dashboard` | Upload/task list | Required |
| `/upload` | Video upload | Required |
| `/door-select/{scene_id}` | Door selection (edit mode) | Required |
| `/viewer` | KakaoMap + viewer (readonly) | None |
| `/admin/basemaps` | Basemap management | Admin |

## Commands

```bash
docker-compose up -d                          # Start all services
docker-compose up -d --build frontend backend # Rebuild
docker-compose logs -f backend                # View logs
docker-compose exec backend alembic upgrade head  # DB migration
docker-compose exec backend pytest            # Backend tests
docker-compose exec frontend npm test         # Frontend tests

# GPU server
celery -A celery_app worker -Q training,alignment -c 1
```
