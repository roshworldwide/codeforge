from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from typing import List

from backend.auth import security, decode_token
from backend.models import ExecuteRequest, ExecutionResponse
from backend.docker.executor import execute_code
from backend.database import get_db

router = APIRouter(prefix="/api", tags=["Execution"])


@router.post("/execute", response_model=ExecutionResponse)
async def execute(
    req: ExecuteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Execute code in a sandboxed environment."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    result = await execute_code(
        code=req.code,
        language=req.language,
        stdin=req.stdin,
    )

    execution = await db.execution.create(
        data={
            "code": req.code,
            "language": req.language,
            "stdin": req.stdin,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exitCode": result["exit_code"],
            "status": result["status"],
            "duration": result["duration"],
            "userId": payload["sub"],
            "roomId": req.roomId,
        }
    )

    return ExecutionResponse(
        id=execution.id,
        stdout=execution.stdout,
        stderr=execution.stderr,
        exitCode=execution.exitCode,
        status=execution.status,
        duration=execution.duration,
        language=execution.language,
        createdAt=execution.createdAt,
    )


@router.get("/executions", response_model=List[ExecutionResponse])
async def list_executions(
    room_id: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """List recent code executions."""
    payload = decode_token(credentials.credentials)
    db = get_db()

    where = {"userId": payload["sub"]}
    if room_id:
        where["roomId"] = room_id

    executions = await db.execution.find_many(
        where=where,
        order={"createdAt": "desc"},
        take=20,
    )

    return [
        ExecutionResponse(
            id=e.id,
            stdout=e.stdout,
            stderr=e.stderr,
            exitCode=e.exitCode,
            status=e.status,
            duration=e.duration,
            language=e.language,
            createdAt=e.createdAt,
        )
        for e in executions
    ]
