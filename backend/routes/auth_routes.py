import random
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    security,
    decode_token,
)
from backend.models import RegisterRequest, LoginRequest, AuthResponse, UserResponse
from backend.database import get_db

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

AVATAR_COLORS = [
    "#6366f1", "#8b5cf6", "#a855f7", "#d946ef", "#ec4899",
    "#f43f5e", "#ef4444", "#f97316", "#eab308", "#22c55e",
    "#14b8a6", "#06b6d4", "#3b82f6", "#0ea5e9", "#10b981",
]


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """Register a new user account."""
    db = get_db()

    existing = await db.user.find_first(
        where={"username": req.username}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    existing_email = await db.user.find_first(
        where={"email": req.email}
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = await db.user.create(
        data={
            "username": req.username,
            "email": req.email,
            "passwordHash": hash_password(req.password),
            "displayName": req.displayName,
            "avatarColor": random.choice(AVATAR_COLORS),
        }
    )

    token = create_access_token(user.id, user.username)

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            displayName=user.displayName,
            avatarColor=user.avatarColor,
            createdAt=user.createdAt,
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Authenticate user and return JWT."""
    db = get_db()

    user = await db.user.find_first(
        where={"username": req.username}
    )

    if not user or not verify_password(req.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user.id, user.username)

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            displayName=user.displayName,
            avatarColor=user.avatarColor,
            createdAt=user.createdAt,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get the current authenticated user's profile."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    user = await db.user.find_unique(where={"id": payload["sub"]})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        displayName=user.displayName,
        avatarColor=user.avatarColor,
        createdAt=user.createdAt,
    )
