#!/usr/bin/env python3

import os
import sys
import time
import signal
import subprocess
import argparse
import threading
from pathlib import Path


class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN= "\033[42m"
    BG_RED  = "\033[41m"


def banner():
    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ⟨/⟩  C O D E F O R G E    L I V E    D E M O              ║
║                                                              ║
║   Collaborative Coding & Debugging Platform                  ║
║   Real-time editing • Docker sandbox • Liquid Glass UI       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}
""")


def status(emoji, msg, color=C.WHITE):
    print(f"  {emoji}  {color}{msg}{C.RESET}")


def section_break():
    print(f"  {C.DIM}{'─' * 56}{C.RESET}")


def big_url_box(url, label="SHARE THIS URL"):
    width = max(len(url) + 8, len(label) + 8, 52)
    pad_url = url.center(width - 4)
    pad_label = label.center(width - 4)
    border = "═" * (width - 2)

    print(f"""
{C.BOLD}{C.GREEN}  ╔{border}╗
  ║{pad_label}║
  ╠{border}╣
  ║                                                    ║
  ║  {C.CYAN}{C.BOLD}{url}{C.GREEN}{C.BOLD}{' ' * (width - 6 - len(url))}║
  ║                                                    ║
  ╚{border}╝{C.RESET}
""")


def check_venv():
    venv_path = Path(__file__).parent / "venv"
    if venv_path.exists() and not hasattr(sys, "real_prefix") and not (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
        status("⚠️", "Virtual environment not activated! Activating...", C.YELLOW)
        activate_path = venv_path / "bin" / "activate"
        print(f"\n  {C.YELLOW}Run this first:{C.RESET}")
        print(f"  {C.CYAN}source {activate_path}{C.RESET}\n")
        sys.exit(1)


def check_database():
    db_path = Path(__file__).parent / "dev.db"
    if not db_path.exists():
        status("🔧", "Database not found — running Prisma push...", C.YELLOW)
        subprocess.run(
            [sys.executable, "-m", "prisma", "db", "push", "--schema=prisma/schema.prisma"],
            cwd=str(Path(__file__).parent),
            check=True,
            capture_output=True,
        )
        status("✅", "Database created", C.GREEN)
    else:
        status("✅", "SQLite database found", C.GREEN)


def check_docker():
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            status("🐳", f"Docker {result.stdout.strip()} — sandboxed execution ON", C.GREEN)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["/usr/local/bin/docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            status("🐳", f"Docker {result.stdout.strip()} — sandboxed execution ON", C.GREEN)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    status("⚠️", "Docker not found — using subprocess fallback", C.YELLOW)
    return False


def start_server(port):
    env = os.environ.copy()
    env["DOCKER_ENABLED"] = "true"

    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--reload",
        ],
        cwd=str(Path(__file__).parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return process


def stream_server_output(process):
    def _stream():
        try:
            for line in iter(process.stdout.readline, b""):
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    print(f"  {C.DIM}│ {decoded}{C.RESET}")
        except (ValueError, OSError):
            pass

    thread = threading.Thread(target=_stream, daemon=True)
    thread.start()
    return thread


def start_ngrok(port):
    try:
        from pyngrok import ngrok, conf

        status("🌐", "Opening ngrok tunnel...", C.CYAN)

        pyngrok_config = conf.get_default()

        tunnel = ngrok.connect(port, "http", bind_tls=True)
        public_url = tunnel.public_url

        return tunnel, public_url

    except ImportError:
        print(f"\n  {C.RED}✗ pyngrok not installed!{C.RESET}")
        print(f"  {C.YELLOW}Install it: pip install pyngrok{C.RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n  {C.RED}✗ Ngrok error: {e}{C.RESET}")
        print(f"  {C.YELLOW}Make sure ngrok is authenticated:{C.RESET}")
        print(f"  {C.CYAN}ngrok config add-authtoken YOUR_TOKEN{C.RESET}\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="CodeForge Live Demo Launcher")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--local", action="store_true", help="Localhost only — skip ngrok")
    args = parser.parse_args()

    banner()

    status("🔍", "Running preflight checks...", C.BLUE)
    section_break()
    check_venv()
    check_database()
    has_docker = check_docker()
    section_break()

    status("🚀", f"Starting FastAPI server on port {args.port}...", C.BLUE)
    server_proc = start_server(args.port)

    time.sleep(3)

    if server_proc.poll() is not None:
        print(f"\n  {C.RED}✗ Server failed to start!{C.RESET}\n")
        sys.exit(1)

    status("✅", f"Server running on http://0.0.0.0:{args.port}", C.GREEN)
    section_break()

    tunnel = None
    if not args.local:
        tunnel, public_url = start_ngrok(args.port)
        status("✅", "Ngrok tunnel established", C.GREEN)
        section_break()

        big_url_box(public_url, "🚀 LIVE DEMO ACTIVE — SHARE THIS URL WITH THE CLASS")

        print(f"  {C.BOLD}{C.WHITE}Quick Info:{C.RESET}")
        print(f"  {C.DIM}├{C.RESET} Local:     {C.CYAN}http://localhost:{args.port}{C.RESET}")
        print(f"  {C.DIM}├{C.RESET} Public:    {C.GREEN}{C.BOLD}{public_url}{C.RESET}")
        print(f"  {C.DIM}├{C.RESET} Docker:    {C.GREEN if has_docker else C.YELLOW}{'✅ Sandboxed' if has_docker else '⚠️ Subprocess fallback'}{C.RESET}")
        print(f"  {C.DIM}├{C.RESET} Timeout:   {C.WHITE}5 seconds per execution{C.RESET}")
        print(f"  {C.DIM}└{C.RESET} Languages: {C.WHITE}Python, C++, JavaScript{C.RESET}")
        print()
        section_break()
        print(f"  {C.BOLD}📋 Presentation Steps:{C.RESET}")
        print(f"  {C.DIM}1.{C.RESET} Share the URL above with the class")
        print(f"  {C.DIM}2.{C.RESET} Each student registers their own account")
        print(f"  {C.DIM}3.{C.RESET} Create a room — students join via the sidebar")
        print(f"  {C.DIM}4.{C.RESET} Edit code simultaneously — see multi-cursor sync live")
        print(f"  {C.DIM}5.{C.RESET} Press {C.CYAN}⌘+Enter{C.RESET} to run code in Docker sandbox")
        print()

    else:
        big_url_box(f"http://localhost:{args.port}", "🖥  LOCAL DEMO ACTIVE")

    print(f"  {C.DIM}Server logs:{C.RESET}")
    stream_server_output(server_proc)

    def shutdown(signum=None, frame=None):
        print(f"\n\n  {C.YELLOW}🛑 Shutting down CodeForge demo...{C.RESET}")

        if tunnel:
            try:
                from pyngrok import ngrok
                ngrok.disconnect(tunnel.public_url)
                ngrok.kill()
                status("✅", "Ngrok tunnel closed", C.GREEN)
            except Exception:
                pass

        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
            status("✅", "Server stopped", C.GREEN)
        except subprocess.TimeoutExpired:
            server_proc.kill()

        print(f"\n  {C.CYAN}Thanks for watching the demo! 👏{C.RESET}\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            if server_proc.poll() is not None:
                print(f"\n  {C.RED}✗ Server process died unexpectedly{C.RESET}")
                shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
