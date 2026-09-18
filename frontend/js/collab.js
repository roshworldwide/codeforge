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


function initCollab(roomId, user) {
  destroyCollab();

  CollabState.roomId = roomId;

  const Y = window.Y || window.yjs;
  if (!Y) {
    console.warn('Y.js not loaded — running in solo mode');
    return null;
  }

  CollabState.doc = new Y.Doc();

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

    CollabState.awareness = CollabState.provider.awareness;

    CollabState.awareness.setLocalStateField('user', {
      name: user.displayName,
      color: user.avatarColor,
      userId: user.id,
    });

    CollabState.provider.on('status', ({ status }) => {
      CollabState.connected = status === 'connected';
      if (CollabState.onConnectionChange) {
        CollabState.onConnectionChange(CollabState.connected);
      }
    });

    CollabState.awareness.on('change', () => {
      updateParticipants();
    });

    updateParticipants();

  } catch (err) {
    console.error('Failed to initialize collaboration:', err);
  }

  return CollabState.doc;
}


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


function getSharedText() {
  if (!CollabState.doc) return null;

  const Y = window.Y || window.yjs;
  if (!Y) return null;

  return CollabState.doc.getText('monaco');
}


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
