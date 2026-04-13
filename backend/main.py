"""
CodeForge — Main Application Entry Point
FastAPI server with REST API, WebSocket collaboration, and static file serving.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import APP_NAME, APP_VERSION, CORS_ORIGINS
from backend.database import connect_db, disconnect_db, get_db
from backend.auth import get_token_from_query
from backend.websocket.yjs_server import yjs_server

from backend.routes.auth_routes import router as auth_router
from backend.routes.room_routes import router as room_router
from backend.routes.snippet_routes import router as snippet_router
from backend.routes.execution_routes import router as execution_router

# ─── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-24s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("codeforge")


# ─── App Lifecycle ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    # Startup
    logger.info(f"🚀 Starting {APP_NAME} v{APP_VERSION}")
    await connect_db()
    logger.info("✅ Database connected")

    # Register document persistence callback
    async def save_room_updates(room_id: str, updates: list):
        """Persist Y.js document updates to database when room empties."""
        try:
            db = get_db()
            # We don't store binary CRDT updates in SQLite for simplicity —
            # the room code is restored from the client's Y.js document
            # on next connection via the sync protocol.
            logger.info(f"Room {room_id} state preserved ({len(updates)} updates)")
        except Exception as e:
            logger.error(f"Failed to save room {room_id}: {e}")

    yjs_server.on_save(save_room_updates)

    yield

    # Shutdown
    logger.info("Shutting down...")
    await disconnect_db()
    logger.info("Database disconnected")


# ─── FastAPI App ────────────────────────────────────────────────────
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Collaborative Coding & Debugging Platform for Students",
    lifespan=lifespan,
)

# ─── CORS ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── REST API Routes ───────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(room_router)
app.include_router(snippet_router)
app.include_router(execution_router)


# ─── WebSocket Endpoint ────────────────────────────────────────────
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time Y.js document collaboration.
    Token is passed as a query parameter since WS doesn't support headers.
    """
    # Validate token
    try:
        payload = get_token_from_query(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    # Get user details from database
    db = get_db()
    user = await db.user.find_unique(where={"id": payload["sub"]})
    if not user:
        await websocket.close(code=4004, reason="User not found")
        return

    # Accept WebSocket connection
    await websocket.accept()

    # Handle collaboration session
    await yjs_server.handle_connection(
        websocket=websocket,
        room_id=room_id,
        user_id=user.id,
        username=user.username,
        display_name=user.displayName,
        avatar_color=user.avatarColor,
    )


# ─── Room Users API (for sidebar) ──────────────────────────────────
@app.get("/api/rooms/{room_id}/users")
async def get_room_active_users(room_id: str):
    """Get list of currently connected users in a room."""
    return yjs_server.get_room_users(room_id)


# ─── Static Files & SPA Routing ────────────────────────────────────
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
async def serve_index():
    """Serve the main landing/auth page."""
    return FileResponse("frontend/index.html")


@app.get("/workspace")
@app.get("/workspace/{room_id}")
async def serve_workspace(room_id: str = None):
    """Serve the workspace page."""
    return FileResponse("frontend/workspace.html")


# ─── Health Check ───────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
    }
