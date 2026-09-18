from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from typing import List

from backend.auth import security, decode_token
from backend.models import CreateSnippetRequest, SnippetResponse
from backend.database import get_db

router = APIRouter(prefix="/api/snippets", tags=["Snippets"])


@router.post("/", response_model=SnippetResponse, status_code=status.HTTP_201_CREATED)
async def create_snippet(
    req: CreateSnippetRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Save a code snippet."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    snippet = await db.codesnippet.create(
        data={
            "title": req.title,
            "code": req.code,
            "language": req.language,
            "userId": payload["sub"],
            "roomId": req.roomId,
        }
    )

    return SnippetResponse(
        id=snippet.id,
        title=snippet.title,
        code=snippet.code,
        language=snippet.language,
        createdAt=snippet.createdAt,
        userId=snippet.userId,
        roomId=snippet.roomId,
    )


@router.get("", response_model=List[SnippetResponse])
async def list_snippets(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """List all snippets for the current user."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    snippets = await db.codesnippet.find_many(
        where={"userId": payload["sub"]},
        order={"createdAt": "desc"},
    )

    return [
        SnippetResponse(
            id=s.id,
            title=s.title,
            code=s.code,
            language=s.language,
            createdAt=s.createdAt,
            userId=s.userId,
            roomId=s.roomId,
        )
        for s in snippets
    ]


@router.get("/{snippet_id}", response_model=SnippetResponse)
async def get_snippet(
    snippet_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get a specific snippet by ID."""
    db = get_db()

    snippet = await db.codesnippet.find_unique(where={"id": snippet_id})
    if not snippet:
        raise HTTPException(status_code=404, detail="Snippet not found")

    return SnippetResponse(
        id=snippet.id,
        title=snippet.title,
        code=snippet.code,
        language=snippet.language,
        createdAt=snippet.createdAt,
        userId=snippet.userId,
        roomId=snippet.roomId,
    )


@router.delete("/{snippet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snippet(
    snippet_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Delete a snippet (owner only)."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    snippet = await db.codesnippet.find_unique(where={"id": snippet_id})
    if not snippet:
        raise HTTPException(status_code=404, detail="Snippet not found")
    if snippet.userId != payload["sub"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this snippet")

    await db.codesnippet.delete(where={"id": snippet_id})
