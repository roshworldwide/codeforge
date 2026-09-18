const EditorState = {
  editor: null,
  model: null,
  currentLanguage: 'python',
  ready: false,
};


const LANGUAGE_MAP = {
  python: 'python',
  cpp: 'cpp',
  javascript: 'javascript',
};

const DEFAULT_CODE = {
  python: '# Welcome to CodeForge! 🔥\n# Write your Python code here and press Run.\n\ndef greet(name):\n    return f"Hello, {name}! Welcome to CodeForge."\n\nprint(greet("Student"))\n',
  cpp: '// Welcome to CodeForge! 🔥\n// Write your C++ code here and press Run.\n\n#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello from CodeForge!" << endl;\n    return 0;\n}\n',
  javascript: '// Welcome to CodeForge! 🔥\n// Write your JavaScript code here and press Run.\n\nfunction greet(name) {\n  return `Hello, ${name}! Welcome to CodeForge.`;\n}\n\nconsole.log(greet("Student"));\n',
};


function initEditor(containerId, language = 'python') {
  return new Promise((resolve) => {
    require.config({
      paths: {
        vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs',
      },
    });

    require(['vs/editor/editor.main'], function () {
      monaco.editor.defineTheme('codeforge-dark', {
        base: 'vs-dark',
        inherit: true,
        rules: [
          { token: '', foreground: 'e4e4e7' },
          { token: 'comment', foreground: '6b7280', fontStyle: 'italic' },
          { token: 'keyword', foreground: 'c084fc' },
          { token: 'string', foreground: '86efac' },
          { token: 'number', foreground: 'fcd34d' },
          { token: 'type', foreground: '67e8f9' },
          { token: 'function', foreground: '93c5fd' },
          { token: 'variable', foreground: 'e4e4e7' },
          { token: 'operator', foreground: 'f9a8d4' },
          { token: 'delimiter', foreground: '9ca3af' },
        ],
        colors: {
          'editor.background': '#00000000',
          'editor.foreground': '#e4e4e7',
          'editor.lineHighlightBackground': '#ffffff08',
          'editor.selectionBackground': '#6366f140',
          'editor.selectionHighlightBackground': '#6366f120',
          'editor.inactiveSelectionBackground': '#6366f120',
          'editorCursor.foreground': '#a5b4fc',
          'editorLineNumber.foreground': '#4b5563',
          'editorLineNumber.activeForeground': '#9ca3af',
          'editorIndentGuide.background': '#ffffff08',
          'editorIndentGuide.activeBackground': '#ffffff15',
          'editor.findMatchBackground': '#f59e0b30',
          'editor.findMatchHighlightBackground': '#f59e0b15',
          'editorWidget.background': '#1a1a2e',
          'editorWidget.border': '#ffffff15',
          'editorSuggestWidget.background': '#1a1a2eee',
          'editorSuggestWidget.border': '#ffffff12',
          'editorSuggestWidget.selectedBackground': '#6366f130',
          'editorHoverWidget.background': '#1a1a2eee',
          'editorHoverWidget.border': '#ffffff12',
          'minimap.background': '#00000000',
          'scrollbar.shadow': '#00000000',
          'scrollbarSlider.background': '#ffffff10',
          'scrollbarSlider.hoverBackground': '#ffffff20',
          'scrollbarSlider.activeBackground': '#ffffff30',
        },
      });

      EditorState.editor = monaco.editor.create(
        document.getElementById(containerId),
        {
          value: DEFAULT_CODE[language] || DEFAULT_CODE.python,
          language: LANGUAGE_MAP[language] || 'python',
          theme: 'codeforge-dark',
          fontSize: 14,
          fontFamily: "'SF Mono', 'Fira Code', 'JetBrains Mono', 'Cascadia Code', monospace",
          fontLigatures: true,
          lineHeight: 22,
          letterSpacing: 0.3,
          padding: { top: 16, bottom: 16 },
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          renderLineHighlight: 'line',
          renderWhitespace: 'selection',
          smoothScrolling: true,
          cursorBlinking: 'smooth',
          cursorSmoothCaretAnimation: 'on',
          cursorWidth: 2,
          bracketPairColorization: { enabled: true },
          automaticLayout: true,
          wordWrap: 'on',
          tabSize: 4,
          insertSpaces: true,
          folding: true,
          glyphMargin: false,
          lineNumbers: 'on',
          lineDecorationsWidth: 8,
          overviewRulerBorder: false,
          overviewRulerLanes: 0,
          hideCursorInOverviewRuler: true,
          guides: {
            indentation: true,
            highlightActiveIndentation: true,
          },
        }
      );

      EditorState.model = EditorState.editor.getModel();
      EditorState.currentLanguage = language;
      EditorState.ready = true;

      EditorState.editor.addCommand(
        monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
        () => {
          document.getElementById('runBtn')?.click();
        }
      );

      EditorState.editor.addCommand(
        monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
        (e) => {
          document.getElementById('saveSnippetBtn')?.click();
        }
      );

      resolve(EditorState.editor);
    });
  });
}


function bindEditorToCollab() {
  if (!EditorState.editor || !CollabState.doc) return;

  const MonacoBinding = window.MonacoBinding ||
    (window.y_monaco && window.y_monaco.MonacoBinding);

  if (!MonacoBinding) {
    console.warn('y-monaco not loaded — collaborative binding skipped');
    return;
  }

  const yText = getSharedText();
  if (!yText) return;

  try {
    CollabState.binding = new MonacoBinding(
      yText,
      EditorState.editor.getModel(),
      new Set([EditorState.editor]),
      CollabState.awareness
    );
    console.log('✅ Monaco bound to Y.js CRDT');
  } catch (err) {
    console.error('Failed to bind Monaco to Y.js:', err);
  }
}


function setEditorLanguage(language) {
  if (!EditorState.editor) return;

  const monacoLang = LANGUAGE_MAP[language] || 'python';
  monaco.editor.setModelLanguage(EditorState.model, monacoLang);
  EditorState.currentLanguage = language;
}


function getEditorCode() {
  if (!EditorState.editor) return '';
  return EditorState.editor.getValue();
}


function setEditorCode(code) {
  if (!EditorState.editor) return;
  EditorState.editor.setValue(code);
}


function focusEditor() {
  if (EditorState.editor) {
    EditorState.editor.focus();
  }
}
