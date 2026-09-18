from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    displayName: str = Field(..., min_length=1, max_length=50)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    displayName: str
    avatarColor: str
    createdAt: datetime


class CreateRoomRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    language: str = Field("python")
    isPublic: bool = True


class UpdateRoomRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    language: Optional[str] = None
    isPublic: Optional[bool] = None


class RoomResponse(BaseModel):
    id: str
    name: str
    description: str
    language: str
    isPublic: bool
    createdAt: datetime
    updatedAt: datetime
    ownerId: str
    memberCount: int = 0
    owner: Optional[UserResponse] = None


class RoomDetailResponse(RoomResponse):
    members: List["MemberResponse"] = []
    code: str = ""


class MemberResponse(BaseModel):
    id: str
    role: str
    joinedAt: datetime
    user: UserResponse


class CreateSnippetRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., max_length=50000)
    language: str = Field("python")
    roomId: Optional[str] = None


class SnippetResponse(BaseModel):
    id: str
    title: str
    code: str
    language: str
    createdAt: datetime
    userId: str
    roomId: Optional[str] = None


class ExecuteRequest(BaseModel):
    code: str = Field(..., max_length=50000)
    language: str = Field("python")
    stdin: str = Field("", max_length=10000)
    roomId: Optional[str] = None


class ExecutionResponse(BaseModel):
    id: str
    stdout: str
    stderr: str
    exitCode: int
    status: str
    duration: int
    language: str
    createdAt: datetime
