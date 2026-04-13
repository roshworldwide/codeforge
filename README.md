# CodeForge — Collaborative Coding & Debugging Platform

A real-time collaborative coding environment for students, featuring live multi-cursor editing, sandboxed code execution, and an iOS 26 Liquid Glass UI.

## Quick Start

```bash
# One-command setup
chmod +x setup.sh && ./setup.sh

# Start the server
source venv/bin/activate
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in your browser.

## Features

- ⚡ **Real-time Collaboration** — Multiple students edit simultaneously with multi-colored cursors
- 🔒 **Sandboxed Execution** — Run Python & C++ code safely in isolated environments
- 🎨 **iOS 26 Liquid Glass UI** — Premium glassmorphic design with micro-animations
- 📝 **Monaco Editor** — VS Code-grade editing experience in the browser
- 💾 **Code Snippets** — Save and share code across sessions
- 👥 **Room System** — Create collaborative workspaces for team projects

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+ / FastAPI / Uvicorn |
| Database | SQLite via Prisma Client Python |
| Real-time | WebSocket + Y.js CRDT |
| Frontend | Vanilla HTML/CSS/JS + Monaco Editor |
| Execution | Docker containers (with subprocess fallback) |

## Project Structure

```
SEProject/
├── backend/                 # FastAPI Python backend
│   ├── main.py              # App entry point + WebSocket endpoint
│   ├── auth.py              # JWT authentication
│   ├── config.py            # Configuration
│   ├── database.py          # Prisma client management
│   ├── models.py            # Pydantic schemas
│   ├── routes/              # REST API endpoints
│   ├── websocket/           # Y.js sync server
│   └── docker/              # Code execution engine
├── frontend/                # Static web frontend
│   ├── index.html           # Auth page
│   ├── workspace.html       # Collaborative workspace
│   ├── css/                 # iOS 26 Liquid Glass design system
│   └── js/                  # Editor, terminal, collaboration
├── prisma/
│   └── schema.prisma        # Database schema
├── docker/sandbox/          # Execution sandbox Dockerfile
├── requirements.txt
├── setup.sh                 # One-command setup
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Sign in |
| GET | `/api/auth/me` | Current user profile |
| POST | `/api/rooms/` | Create room |
| GET | `/api/rooms` | List rooms |
| GET | `/api/rooms/:id` | Room details |
| POST | `/api/rooms/:id/join` | Join room |
| POST | `/api/execute` | Run code |
| POST | `/api/snippets/` | Save snippet |
| GET | `/api/snippets` | List snippets |
| WS | `/ws/:room_id` | Y.js collaboration |

## License

MIT — Built for academic use.
