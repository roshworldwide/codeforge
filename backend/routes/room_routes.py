"""
CodeForge Room Routes
POST   /api/rooms         — Create room
GET    /api/rooms         — List public rooms
GET    /api/rooms/{id}    — Get room details
PUT    /api/rooms/{id}    — Update room
DELETE /api/rooms/{id}    — Delete room
POST   /api/rooms/{id}/join — Join room
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from typing import List

from backend.auth import security, decode_token
from backend.models import (
    CreateRoomRequest,
    UpdateRoomRequest,
    RoomResponse,
    RoomDetailResponse,
    UserResponse,
    MemberResponse,
)
from backend.database import get_db

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    req: CreateRoomRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Create a new collaborative coding room."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    room = await db.room.create(
        data={
            "name": req.name,
            "description": req.description,
            "language": req.language,
            "isPublic": req.isPublic,
            "ownerId": payload["sub"],
        },
    )

    # Auto-add owner as a member
    await db.roommember.create(
        data={
            "userId": payload["sub"],
            "roomId": room.id,
            "role": "owner",
        }
    )

    return RoomResponse(
        id=room.id,
        name=room.name,
        description=room.description,
        language=room.language,
        isPublic=room.isPublic,
        createdAt=room.createdAt,
        updatedAt=room.updatedAt,
        ownerId=room.ownerId,
        memberCount=1,
    )


@router.get("", response_model=List[RoomResponse])
async def list_rooms(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """List all public rooms and rooms user is a member of."""
    payload = decode_token(credentials.credentials)
    db = get_db()
    user_id = payload["sub"]

    # Get public rooms and rooms user belongs to
    rooms = await db.room.find_many(
        where={
            "OR": [
                {"isPublic": True},
                {"members": {"some": {"userId": user_id}}},
            ]
        },
        include={
            "owner": True,
            "members": True,
        },
        order={"updatedAt": "desc"},
    )

    return [
        RoomResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            language=r.language,
            isPublic=r.isPublic,
            createdAt=r.createdAt,
            updatedAt=r.updatedAt,
            ownerId=r.ownerId,
            memberCount=len(r.members) if r.members else 0,
            owner=UserResponse(
                id=r.owner.id,
                username=r.owner.username,
                email=r.owner.email,
                displayName=r.owner.displayName,
                avatarColor=r.owner.avatarColor,
                createdAt=r.owner.createdAt,
            ) if r.owner else None,
        )
        for r in rooms
    ]


@router.get("/{room_id}", response_model=RoomDetailResponse)
async def get_room(
    room_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get full room details including members and code."""
    db = get_db()

    room = await db.room.find_unique(
        where={"id": room_id},
        include={
            "owner": True,
            "members": {"include": {"user": True}},
        },
    )

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    return RoomDetailResponse(
        id=room.id,
        name=room.name,
        description=room.description,
        language=room.language,
        isPublic=room.isPublic,
        createdAt=room.createdAt,
        updatedAt=room.updatedAt,
        ownerId=room.ownerId,
        code=room.code,
        memberCount=len(room.members) if room.members else 0,
        owner=UserResponse(
            id=room.owner.id,
            username=room.owner.username,
            email=room.owner.email,
            displayName=room.owner.displayName,
            avatarColor=room.owner.avatarColor,
            createdAt=room.owner.createdAt,
        ) if room.owner else None,
        members=[
            MemberResponse(
                id=m.id,
                role=m.role,
                joinedAt=m.joinedAt,
                user=UserResponse(
                    id=m.user.id,
                    username=m.user.username,
                    email=m.user.email,
                    displayName=m.user.displayName,
                    avatarColor=m.user.avatarColor,
                    createdAt=m.user.createdAt,
                ),
            )
            for m in (room.members or [])
        ],
    )


@router.put("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: str,
    req: UpdateRoomRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Update room settings (owner only)."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    room = await db.room.find_unique(where={"id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.ownerId != payload["sub"]:
        raise HTTPException(status_code=403, detail="Only the room owner can update settings")

    update_data = {k: v for k, v in req.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = await db.room.update(
        where={"id": room_id},
        data=update_data,
    )

    return RoomResponse(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        language=updated.language,
        isPublic=updated.isPublic,
        createdAt=updated.createdAt,
        updatedAt=updated.updatedAt,
        ownerId=updated.ownerId,
    )


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Delete a room (owner only)."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    room = await db.room.find_unique(where={"id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.ownerId != payload["sub"]:
        raise HTTPException(status_code=403, detail="Only the room owner can delete this room")

    await db.room.delete(where={"id": room_id})


@router.post("/{room_id}/join", response_model=dict)
async def join_room(
    room_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Join an existing room."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    room = await db.room.find_unique(where={"id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check if already a member
    existing = await db.roommember.find_first(
        where={"userId": payload["sub"], "roomId": room_id}
    )
    if existing:
        return {"message": "Already a member", "role": existing.role}

    await db.roommember.create(
        data={
            "userId": payload["sub"],
            "roomId": room_id,
            "role": "editor",
        }
    )

    return {"message": "Joined room successfully", "role": "editor"}
