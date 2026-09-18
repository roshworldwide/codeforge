function initSidebar() {
  const createBtn = document.getElementById('createRoomBtn');
  if (createBtn) {
    createBtn.addEventListener('click', showCreateRoomModal);
  }

  const cancelBtn = document.getElementById('cancelCreateRoom');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', hideCreateRoomModal);
  }

  const backdrop = document.getElementById('createRoomBackdrop');
  if (backdrop) {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) hideCreateRoomModal();
    });
  }

  const form = document.getElementById('createRoomForm');
  if (form) {
    form.addEventListener('submit', handleCreateRoom);
  }

  loadRooms();
  loadSnippets();
}


async function loadRooms() {
  const container = document.getElementById('roomList');
  if (!container) return;

  try {
    const rooms = await api('/api/rooms');

    if (!rooms || rooms.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="padding: var(--space-4);">
          <p style="font-size: var(--font-xs); color: var(--text-tertiary);">
            No rooms yet. Create one to get started!
          </p>
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    const list = document.createElement('ul');
    list.className = 'room-list';

    rooms.forEach((room, i) => {
      const li = document.createElement('li');
      li.className = `room-item slide-up stagger-${Math.min(i + 1, 6)}`;
      li.dataset.roomId = room.id;
      li.style.animationFillMode = 'both';

      const isActive = AppState.currentRoom?.id === room.id;
      if (isActive) li.classList.add('active');

      li.innerHTML = `
        <span class="room-item-icon">${room.isPublic ? '🌐' : '🔒'}</span>
        <span class="room-item-name">${escapeHtml(room.name)}</span>
        <span class="room-item-count">${room.memberCount || 0}</span>
      `;

      li.addEventListener('click', () => joinAndOpenRoom(room));
      list.appendChild(li);
    });

    container.appendChild(list);
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state" style="padding: var(--space-4);">
        <p style="font-size: var(--font-xs); color: var(--color-error);">
          Failed to load rooms
        </p>
      </div>
    `;
  }
}


async function joinAndOpenRoom(room) {
  try {
    await api(`/api/rooms/${room.id}/join`, { method: 'POST' });

    const fullRoom = await api(`/api/rooms/${room.id}`);
    AppState.currentRoom = fullRoom;

    const roomNameInput = document.getElementById('roomNameInput');
    if (roomNameInput) roomNameInput.value = fullRoom.name;

    const langSelect = document.getElementById('languageSelect');
    if (langSelect) langSelect.value = fullRoom.language;

    document.querySelectorAll('.room-item').forEach((el) => {
      el.classList.toggle('active', el.dataset.roomId === room.id);
    });

    setEditorLanguage(fullRoom.language);

    initCollab(room.id, AppState.user);

    setTimeout(() => {
      bindEditorToCollab();
    }, 500);

    showToast(`Joined room: ${fullRoom.name}`);
  } catch (err) {
    showToast(`Failed to join room: ${err.message}`, 'error');
  }
}


function updateUserList(participants) {
  const container = document.getElementById('userList');
  const countBadge = document.getElementById('onlineCount');

  if (!container) return;

  if (countBadge) {
    countBadge.textContent = participants.length;
  }

  if (participants.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: var(--space-4);">
        <p style="font-size: var(--font-xs); color: var(--text-tertiary);">
          Join a room to see participants
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  const list = document.createElement('ul');
  list.className = 'user-list';

  participants.forEach((p) => {
    const li = document.createElement('li');
    li.className = 'user-item';
    li.innerHTML = `
      <div class="avatar" style="background-color: ${p.color};">
        ${getInitials(p.name)}
      </div>
      <div class="user-item-info">
        <span class="user-item-name">${escapeHtml(p.name)}</span>
      </div>
      <div class="user-item-cursor" style="background-color: ${p.color};"></div>
    `;
    list.appendChild(li);
  });

  container.appendChild(list);

  updateParticipantBar(participants);
}


function updateParticipantBar(participants) {
  const bar = document.getElementById('participantsBar');
  if (!bar) return;

  bar.innerHTML = '';
  const stack = document.createElement('div');
  stack.className = 'avatar-stack';

  participants.slice(0, 5).forEach((p) => {
    const avatar = document.createElement('div');
    avatar.className = 'avatar avatar-sm';
    avatar.style.backgroundColor = p.color;
    avatar.textContent = getInitials(p.name);
    avatar.title = p.name;
    stack.appendChild(avatar);
  });

  if (participants.length > 5) {
    const more = document.createElement('div');
    more.className = 'avatar avatar-sm';
    more.style.backgroundColor = '#374151';
    more.textContent = `+${participants.length - 5}`;
    stack.appendChild(more);
  }

  bar.appendChild(stack);
}


async function loadSnippets() {
  const container = document.getElementById('snippetList');
  if (!container) return;

  try {
    const snippets = await api('/api/snippets');

    if (!snippets || snippets.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="padding: var(--space-4);">
          <p style="font-size: var(--font-xs); color: var(--text-tertiary);">
            Save code snippets for later
          </p>
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    snippets.forEach((snippet) => {
      const card = document.createElement('div');
      card.className = 'snippet-card';
      card.innerHTML = `
        <div class="snippet-title">${escapeHtml(snippet.title)}</div>
        <div class="snippet-meta">${snippet.language} · ${timeAgo(snippet.createdAt)}</div>
        <div class="snippet-preview">${escapeHtml(snippet.code.substring(0, 100))}${snippet.code.length > 100 ? '...' : ''}</div>
      `;
      card.addEventListener('click', () => {
        setEditorCode(snippet.code);
        setEditorLanguage(snippet.language);
        const langSelect = document.getElementById('languageSelect');
        if (langSelect) langSelect.value = snippet.language;
        showToast(`Loaded snippet: ${snippet.title}`);
      });
      container.appendChild(card);
    });
  } catch (err) {
  }
}


function showCreateRoomModal() {
  const backdrop = document.getElementById('createRoomBackdrop');
  if (backdrop) backdrop.classList.remove('hidden');
  document.getElementById('newRoomName')?.focus();
}


function hideCreateRoomModal() {
  const backdrop = document.getElementById('createRoomBackdrop');
  if (backdrop) backdrop.classList.add('hidden');
  document.getElementById('createRoomForm')?.reset();
}


async function handleCreateRoom(e) {
  e.preventDefault();

  const name = document.getElementById('newRoomName')?.value;
  const description = document.getElementById('newRoomDesc')?.value || '';
  const language = document.getElementById('newRoomLang')?.value || 'python';

  if (!name) return;

  try {
    const room = await api('/api/rooms/', {
      method: 'POST',
      body: { name, description, language, isPublic: true },
    });

    hideCreateRoomModal();
    showToast(`Room "${name}" created!`);
    await loadRooms();
    joinAndOpenRoom(room);
  } catch (err) {
    showToast(`Failed to create room: ${err.message}`, 'error');
  }
}


async function saveSnippet() {
  const code = getEditorCode();
  if (!code.trim()) {
    showToast('Nothing to save', 'error');
    return;
  }

  const title = prompt('Snippet name:');
  if (!title) return;

  try {
    await api('/api/snippets/', {
      method: 'POST',
      body: {
        title,
        code,
        language: EditorState.currentLanguage,
        roomId: AppState.currentRoom?.id || null,
      },
    });

    showToast(`Snippet "${title}" saved!`);
    loadSnippets();
  } catch (err) {
    showToast(`Failed to save snippet: ${err.message}`, 'error');
  }
}


function escapeHtml(text) {
  const el = document.createElement('span');
  el.textContent = text;
  return el.innerHTML;
}
