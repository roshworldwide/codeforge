document.addEventListener('DOMContentLoaded', async () => {
  if (!document.getElementById('workspace')) return;

  if (!requireAuth()) return;

  console.log('🔥 CodeForge Workspace initializing...');

  try {
    await initEditor('editorContainer', 'python');
    console.log('✅ Monaco Editor ready');
  } catch (err) {
    console.error('Failed to initialize editor:', err);
    showToast('Editor failed to load. Please refresh.', 'error');
  }

  initTerminal();
  console.log('✅ Terminal ready');

  initSidebar();
  console.log('✅ Sidebar ready');

  const runBtn = document.getElementById('runBtn');
  if (runBtn) {
    runBtn.addEventListener('click', executeCode);
  }

  const langSelect = document.getElementById('languageSelect');
  if (langSelect) {
    langSelect.addEventListener('change', (e) => {
      setEditorLanguage(e.target.value);
    });
  }

  const saveBtn = document.getElementById('saveSnippetBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', saveSnippet);
  }

  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', logout);
  }

  const roomNameInput = document.getElementById('roomNameInput');
  if (roomNameInput) {
    roomNameInput.addEventListener('change', async () => {
      if (AppState.currentRoom) {
        try {
          await api(`/api/rooms/${AppState.currentRoom.id}`, {
            method: 'PUT',
            body: { name: roomNameInput.value },
          });
          AppState.currentRoom.name = roomNameInput.value;
        } catch (err) {
        }
      }
    });
  }

  CollabState.onParticipantChange = (participants) => {
    updateUserList(participants);
  };

  CollabState.onConnectionChange = (connected) => {
    if (connected) {
      showToast('Connected to room', 'success');
    }
  };

  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      executeCode();
    }

    if (e.key === 'Escape') {
      hideCreateRoomModal();
    }
  });

  const pathParts = window.location.pathname.split('/');
  const urlRoomId = pathParts[pathParts.length - 1];
  if (urlRoomId && urlRoomId !== 'workspace') {
    try {
      const room = await api(`/api/rooms/${urlRoomId}`);
      if (room) {
        joinAndOpenRoom(room);
      }
    } catch (err) {
      console.log('Room from URL not found, starting fresh');
    }
  }

  if (!AppState.currentRoom) {
    const output = document.getElementById('terminalOutput');
    if (output) {
      output.innerHTML = `<span class="system">// Welcome to CodeForge, ${AppState.user?.displayName || 'Student'}! 🔥
// Create or join a room from the sidebar to start collaborating.
// Press ⌘+Enter to run your code.
</span>`;
    }
  }

  console.log('🚀 CodeForge Workspace ready!');
});
