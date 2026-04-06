from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    get_current_user,
)
from app.models import User, Session
from app.schemas.auth import (
    TokenResponse,
    RefreshRequest,
    AccessTokenResponse,
    UserResponse,
    LoginUrlResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.get("/login", response_model=LoginUrlResponse)
async def login(request: Request):
    """Google OAuth 로그인 URL 반환"""
    if settings.PUBLIC_BASE_URL:
        callback_url = f"{settings.PUBLIC_BASE_URL}/api/auth/callback"
    else:
        proto = request.headers.get("X-Forwarded-Proto", "http")
        host = request.headers.get("Host", request.base_url.hostname)
        callback_url = f"{proto}://{host}/api/auth/callback"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return LoginUrlResponse(url=url)


@router.get("/callback")
async def callback(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Google 인증 코드로 사용자 정보 취득 → JWT 발급"""
    if settings.PUBLIC_BASE_URL:
        callback_url = f"{settings.PUBLIC_BASE_URL}/api/auth/callback"
    else:
        proto = request.headers.get("X-Forwarded-Proto", "http")
        host = request.headers.get("Host", request.base_url.hostname)
        callback_url = f"{proto}://{host}/api/auth/callback"

    # 1. 인증 코드 → Google Access Token 교환
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": callback_url,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google 인증에 실패했습니다.",
        )

    google_tokens = token_resp.json()
    google_access_token = google_tokens.get("access_token")

    # 2. Google Access Token → 사용자 정보 취득
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google 사용자 정보 취득에 실패했습니다.",
        )

    google_user = userinfo_resp.json()
    google_id = google_user["id"]
    email = google_user["email"]
    name = google_user.get("name", email)
    avatar_url = google_user.get("picture")

    # 3. DB에 사용자 저장/갱신
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )
        db.add(user)
        await db.flush()
    else:
        user.email = email
        user.name = name
        user.avatar_url = avatar_url

    # 4. JWT 발급
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token()

    # 5. Refresh Token을 sessions 테이블에 저장
    session = Session(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await db.commit()

    return RedirectResponse(
        url=f"/login/callback?access_token={access_token}&refresh_token={refresh_token}",
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh Token → 새 Access Token 발급"""
    token_hash = hash_token(body.refresh_token)

    result = await db.execute(
        select(Session).where(
            Session.refresh_token_hash == token_hash,
            Session.is_revoked == False,
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 Refresh Token입니다.",
        )

    if session.expires_at < datetime.now(timezone.utc):
        session.is_revoked = True
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="만료된 Refresh Token입니다.",
        )

    # 사용자 조회
    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
        )

    access_token = create_access_token(str(user.id), user.role.value)

    return AccessTokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refresh Token 무효화 (로그아웃)"""
    token_hash = hash_token(body.refresh_token)

    result = await db.execute(
        select(Session).where(
            Session.refresh_token_hash == token_hash,
            Session.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()

    if session:
        session.is_revoked = True
        await db.commit()

    return None


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보"""
    return user
