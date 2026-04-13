/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  CodeForge — Collaboration Manager                              ║
 * ║  Y.js CRDT document sync + awareness (cursors/presence)         ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

// ─── Collaboration State ───────────────────────────────────────────
const CollabState = {
  doc: null,
  provider: null,
  awareness: null,
  binding: null,
  connected: false,
  roomId: null,
  participants: new Map(),
  onParticipantChange: null,
  onConnectionChange: null,
};


/**
 * Initialize Y.js collaboration for a room.
 * Sets up the CRDT document, WebSocket provider, and awareness protocol.
 */
function initCollab(roomId, user) {
  // Clean up existing connection
  destroyCollab();

  CollabState.roomId = roomId;

  // Create Y.js document
  const Y = window.Y || window.yjs;
  if (!Y) {
    console.warn('Y.js not loaded — running in solo mode');
    return null;
  }

  CollabState.doc = new Y.Doc();

  // Setup WebSocket provider
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}`;

  try {
    const WebsocketProvider = window.WebsocketProvider ||
      (window.y_websocket && window.y_websocket.WebsocketProvider);

    if (!WebsocketProvider) {
      console.warn('y-websocket not loaded — running in solo mode');
      return CollabState.doc;
    }

    CollabState.provider = new WebsocketProvider(
      wsUrl,
      roomId,
      CollabState.doc,
      {
        params: { token: AppState.token },
        connect: true,
        WebSocketPolyfill: WebSocket,
      }
    );

    // Awareness setup
    CollabState.awareness = CollabState.provider.awareness;

    // Set local user state
    CollabState.awareness.setLocalStateField('user', {
      name: user.displayName,
      color: user.avatarColor,
      userId: user.id,
    });

    // Track connection status
    CollabState.provider.on('status', ({ status }) => {
      CollabState.connected = status === 'connected';
      if (CollabState.onConnectionChange) {
        CollabState.onConnectionChange(CollabState.connected);
      }
    });

    // Track participants via awareness
    CollabState.awareness.on('change', () => {
      updateParticipants();
    });

    updateParticipants();

  } catch (err) {
    console.error('Failed to initialize collaboration:', err);
  }

  return CollabState.doc;
}


/**
 * Update the participants map from awareness states.
 */
function updateParticipants() {
  if (!CollabState.awareness) return;

  const states = CollabState.awareness.getStates();
  CollabState.participants.clear();

  states.forEach((state, clientId) => {
    if (state.user) {
      CollabState.participants.set(clientId, {
        clientId,
        ...state.user,
        cursor: state.cursor || null,
      });
    }
  });

  if (CollabState.onParticipantChange) {
    CollabState.onParticipantChange(Array.from(CollabState.participants.values()));
  }
}


/**
 * Get the Y.Text type for the editor.
 */
function getSharedText() {
  if (!CollabState.doc) return null;

  const Y = window.Y || window.yjs;
  if (!Y) return null;

  return CollabState.doc.getText('monaco');
}


/**
 * Clean up collaboration resources.
 */
function destroyCollab() {
  if (CollabState.binding) {
    CollabState.binding.destroy();
    CollabState.binding = null;
  }

  if (CollabState.provider) {
    CollabState.provider.disconnect();
    CollabState.provider.destroy();
    CollabState.provider = null;
  }

  if (CollabState.doc) {
    CollabState.doc.destroy();
    CollabState.doc = null;
  }

  CollabState.awareness = null;
  CollabState.connected = false;
  CollabState.participants.clear();
}
