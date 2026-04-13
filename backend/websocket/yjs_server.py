"""
CodeForge Y.js WebSocket Sync Server
Handles real-time collaborative editing via the Y.js CRDT protocol.

Protocol overview:
- messageSync (0):    Document state synchronization
- messageAwareness (1): Cursor positions and user presence
"""

import asyncio
import json
import struct
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("codeforge.yjs")


# ─── Y.js Protocol Constants ───────────────────────────────────────
MSG_SYNC = 0
MSG_AWARENESS = 1

SYNC_STEP1 = 0  # Request: send your state vector
SYNC_STEP2 = 1  # Response: here are the updates you're missing
SYNC_UPDATE = 2  # Incremental update broadcast


@dataclass
class ClientInfo:
    """Tracks a connected client in a room."""
    websocket: WebSocket
    user_id: str
    username: str
    display_name: str
    avatar_color: str
    client_id: int = 0


@dataclass
class RoomState:
    """Manages the shared state for a collaborative room."""
    room_id: str
    clients: Dict[int, ClientInfo] = field(default_factory=dict)
    # Store document as accumulated binary updates
    document_updates: list = field(default_factory=list)
    # Store latest awareness states
    awareness_states: Dict[int, bytes] = field(default_factory=dict)
    # Client ID counter
    _next_client_id: int = 1

    def add_client(self, info: ClientInfo) -> int:
        """Add a client and return assigned client ID."""
        client_id = self._next_client_id
        self._next_client_id += 1
        info.client_id = client_id
        self.clients[client_id] = info
        return client_id

    def remove_client(self, client_id: int):
        """Remove a client from the room."""
        self.clients.pop(client_id, None)
        self.awareness_states.pop(client_id, None)

    @property
    def is_empty(self) -> bool:
        return len(self.clients) == 0


class YjsSyncServer:
    """
    Manages Y.js document synchronization across WebSocket connections.

    Instead of running a full Y.js CRDT engine in Python, this server acts as
    a smart relay:
    1. Stores all document updates received from any client
    2. Broadcasts updates to all other clients in the same room
    3. Replays stored updates to newly connecting clients
    4. Manages awareness (cursor positions, user presence)

    The actual CRDT merge logic runs in each client's browser via Y.js.
    """

    def __init__(self):
        self.rooms: Dict[str, RoomState] = {}
        self._save_callbacks = []

    def get_or_create_room(self, room_id: str) -> RoomState:
        """Get existing room state or create new one."""
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomState(room_id=room_id)
        return self.rooms[room_id]

    def on_save(self, callback):
        """Register a callback for persisting document state."""
        self._save_callbacks.append(callback)

    async def handle_connection(
        self,
        websocket: WebSocket,
        room_id: str,
        user_id: str,
        username: str,
        display_name: str,
        avatar_color: str,
    ):
        """
        Main WebSocket connection handler for a room.
        Manages the full lifecycle: connect → sync → relay → disconnect.
        """
        room = self.get_or_create_room(room_id)

        client_info = ClientInfo(
            websocket=websocket,
            user_id=user_id,
            username=username,
            display_name=display_name,
            avatar_color=avatar_color,
        )
        client_id = room.add_client(client_info)

        logger.info(
            f"Client {username} (#{client_id}) joined room {room_id}. "
            f"Total clients: {len(room.clients)}"
        )

        try:
            # Send initial sync: replay all stored updates to the new client
            await self._send_initial_sync(websocket, room)

            # Send current awareness states of all other clients
            await self._send_awareness_states(websocket, room, client_id)

            # Broadcast this client's join to others
            await self._broadcast_user_joined(room, client_info)

            # Main message loop
            while True:
                data = await websocket.receive_bytes()
                await self._handle_message(data, room, client_id)

        except WebSocketDisconnect:
            logger.info(f"Client {username} (#{client_id}) disconnected from room {room_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {username} in room {room_id}: {e}")
        finally:
            # Clean up
            room.remove_client(client_id)

            # Broadcast awareness removal
            await self._broadcast_awareness_remove(room, client_id)

            # If room is empty, persist state and optionally clean up
            if room.is_empty:
                await self._persist_room_state(room)

    async def _send_initial_sync(self, websocket: WebSocket, room: RoomState):
        """Send all stored document updates to a newly connected client."""
        for update in room.document_updates:
            # Wrap update in sync protocol: [MSG_SYNC, SYNC_UPDATE, ...update]
            msg = bytes([MSG_SYNC, SYNC_UPDATE]) + update
            try:
                await websocket.send_bytes(msg)
            except Exception:
                pass

    async def _send_awareness_states(
        self, websocket: WebSocket, room: RoomState, exclude_client: int
    ):
        """Send existing awareness states to a new client."""
        for cid, state_data in room.awareness_states.items():
            if cid != exclude_client:
                try:
                    await websocket.send_bytes(state_data)
                except Exception:
                    pass

    async def _handle_message(
        self, data: bytes, room: RoomState, sender_id: int
    ):
        """Parse and route an incoming Y.js protocol message."""
        if len(data) < 1:
            return

        msg_type = data[0]

        if msg_type == MSG_SYNC:
            await self._handle_sync_message(data, room, sender_id)
        elif msg_type == MSG_AWARENESS:
            await self._handle_awareness_message(data, room, sender_id)
        else:
            # Unknown message type — relay as-is for forward compatibility
            await self._broadcast(room, data, exclude=sender_id)

    async def _handle_sync_message(
        self, data: bytes, room: RoomState, sender_id: int
    ):
        """Handle document sync messages (updates)."""
        if len(data) < 2:
            return

        sync_type = data[1]

        if sync_type == SYNC_STEP1:
            # Client requesting sync — send all stored updates
            sender = room.clients.get(sender_id)
            if sender:
                await self._send_initial_sync(sender.websocket, room)

        elif sync_type == SYNC_STEP2 or sync_type == SYNC_UPDATE:
            # Document update — store and broadcast
            update_data = data[2:]
            if update_data:
                room.document_updates.append(update_data)

                # Compact updates periodically to prevent memory bloat
                if len(room.document_updates) > 500:
                    # Keep last 200 updates (CRDT ensures convergence)
                    room.document_updates = room.document_updates[-200:]

                # Broadcast to all other clients
                await self._broadcast(room, data, exclude=sender_id)

    async def _handle_awareness_message(
        self, data: bytes, room: RoomState, sender_id: int
    ):
        """Handle awareness messages (cursor position, user presence)."""
        # Store the latest awareness state for this client
        room.awareness_states[sender_id] = data

        # Broadcast to all other clients
        await self._broadcast(room, data, exclude=sender_id)

    async def _broadcast(
        self, room: RoomState, data: bytes, exclude: Optional[int] = None
    ):
        """Broadcast binary data to all clients in a room except the sender."""
        disconnected = []

        for client_id, client in room.clients.items():
            if client_id == exclude:
                continue
            try:
                await client.websocket.send_bytes(data)
            except Exception:
                disconnected.append(client_id)

        # Clean up disconnected clients
        for cid in disconnected:
            room.remove_client(cid)

    async def _broadcast_user_joined(self, room: RoomState, client: ClientInfo):
        """Broadcast a custom awareness message when a user joins."""
        # Send as awareness update with user metadata
        awareness_data = json.dumps({
            "type": "user_joined",
            "clientId": client.client_id,
            "userId": client.user_id,
            "username": client.username,
            "displayName": client.display_name,
            "avatarColor": client.avatar_color,
        }).encode()

        # Package as awareness message
        msg = bytes([MSG_AWARENESS]) + awareness_data

        for cid, c in room.clients.items():
            if cid != client.client_id:
                try:
                    await c.websocket.send_bytes(msg)
                except Exception:
                    pass

    async def _broadcast_awareness_remove(self, room: RoomState, client_id: int):
        """Broadcast awareness removal when a client disconnects."""
        removal_data = json.dumps({
            "type": "user_left",
            "clientId": client_id,
        }).encode()

        msg = bytes([MSG_AWARENESS]) + removal_data

        for cid, c in room.clients.items():
            try:
                await c.websocket.send_bytes(msg)
            except Exception:
                pass

    async def _persist_room_state(self, room: RoomState):
        """Persist the room's document state when all users disconnect."""
        for callback in self._save_callbacks:
            try:
                await callback(room.room_id, room.document_updates)
            except Exception as e:
                logger.error(f"Failed to persist room {room.room_id}: {e}")

    def get_room_users(self, room_id: str) -> list:
        """Get list of currently connected users in a room."""
        room = self.rooms.get(room_id)
        if not room:
            return []

        return [
            {
                "clientId": c.client_id,
                "userId": c.user_id,
                "username": c.username,
                "displayName": c.display_name,
                "avatarColor": c.avatar_color,
            }
            for c in room.clients.values()
        ]


# ─── Global Singleton ──────────────────────────────────────────────
yjs_server = YjsSyncServer()
