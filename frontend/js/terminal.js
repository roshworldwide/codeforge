const TerminalState = {
  collapsed: false,
  running: false,
};


function initTerminal() {
  const toggleBtn = document.getElementById('toggleTerminal');
  const terminalHeader = document.getElementById('terminalHeader');
  const clearBtn = document.getElementById('clearTerminal');
  const panel = document.getElementById('terminalPanel');

  if (terminalHeader) {
    terminalHeader.addEventListener('click', (e) => {
      if (e.target.closest('.terminal-actions')) return;
      toggleTerminal();
    });
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleTerminal();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      clearTerminalOutput();
    });
  }

  initResizeHandle();
}


function toggleTerminal() {
  const panel = document.getElementById('terminalPanel');
  if (!panel) return;

  TerminalState.collapsed = !TerminalState.collapsed;
  panel.classList.toggle('collapsed', TerminalState.collapsed);

  const icon = document.querySelector('#toggleTerminal svg');
  if (icon) {
    icon.style.transform = TerminalState.collapsed ? 'rotate(180deg)' : '';
  }

  if (EditorState.editor) {
    setTimeout(() => EditorState.editor.layout(), 350);
  }
}


function writeToTerminal(text, type = 'stdout') {
  const output = document.getElementById('terminalOutput');
  if (!output) return;

  const line = document.createElement('span');
  line.className = type;
  line.textContent = text;
  output.appendChild(line);

  const body = document.getElementById('terminalBody');
  if (body) {
    body.scrollTop = body.scrollHeight;
  }

  if (TerminalState.collapsed && text.trim()) {
    toggleTerminal();
  }
}


function clearTerminalOutput() {
  const output = document.getElementById('terminalOutput');
  if (output) {
    output.innerHTML = '<span class="system">// Terminal cleared</span>\n';
  }
}


async function executeCode() {
  if (TerminalState.running) return;

  const code = getEditorCode();
  if (!code.trim()) {
    writeToTerminal('No code to execute.\n', 'system');
    return;
  }

  const runBtn = document.getElementById('runBtn');
  const execStatus = document.getElementById('execStatus');

  TerminalState.running = true;
  if (runBtn) {
    runBtn.classList.add('running');
    runBtn.innerHTML = `
      <div class="spinner" style="width: 14px; height: 14px; border-width: 1.5px;"></div>
      Running...
    `;
  }

  const output = document.getElementById('terminalOutput');
  if (output) {
    output.innerHTML = '';
  }
  writeToTerminal(`▶ Executing ${EditorState.currentLanguage}...\n\n`, 'system');

  if (execStatus) {
    execStatus.style.display = '';
    execStatus.className = 'badge badge-warning';
    execStatus.textContent = 'Running';
  }

  try {
    const result = await api('/api/execute', {
      method: 'POST',
      body: {
        code: code,
        language: EditorState.currentLanguage,
        stdin: '',
        roomId: AppState.currentRoom?.id || null,
      },
    });

    if (result.stdout) {
      writeToTerminal(result.stdout, 'stdout');
    }

    if (result.stderr) {
      writeToTerminal(result.stderr + '\n', 'stderr');
    }

    const statusText = result.status === 'success' ? '✓' : '✗';
    const statusClass = result.status === 'success' ? 'success' : 'stderr';
    writeToTerminal(
      `\n${statusText} Process exited with code ${result.exitCode} (${result.duration}ms)\n`,
      statusClass
    );

    if (execStatus) {
      if (result.status === 'success') {
        execStatus.className = 'badge badge-success';
        execStatus.textContent = `✓ ${result.duration}ms`;
      } else if (result.status === 'timeout') {
        execStatus.className = 'badge badge-warning';
        execStatus.textContent = 'Timeout';
      } else {
        execStatus.className = 'badge badge-error';
        execStatus.textContent = 'Error';
      }
    }

  } catch (err) {
    writeToTerminal(`\n✗ Execution failed: ${err.message}\n`, 'stderr');
    if (execStatus) {
      execStatus.className = 'badge badge-error';
      execStatus.textContent = 'Failed';
    }
  } finally {
    TerminalState.running = false;
    if (runBtn) {
      runBtn.classList.remove('running');
      runBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z"/>
        </svg>
        Run
      `;
    }
  }
}


function initResizeHandle() {
  const handle = document.getElementById('resizeHandle');
  const panel = document.getElementById('terminalPanel');
  const editorContainer = document.getElementById('editorContainer');

  if (!handle || !panel) return;

  let startY, startHeight;

  handle.addEventListener('mousedown', (e) => {
    startY = e.clientY;
    startHeight = panel.offsetHeight;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (e) => {
      const delta = startY - e.clientY;
      const newHeight = Math.min(Math.max(startHeight + delta, 100), 500);
      panel.style.height = newHeight + 'px';

      if (EditorState.editor) {
        EditorState.editor.layout();
      }
    };

    const onMouseUp = () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  });
}
