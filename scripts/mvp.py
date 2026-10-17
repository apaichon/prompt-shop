"""Local-only supervisor for the real portal, ADK and offline Laya services."""
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "tmp/run"
SECRETS = {"GOOGLE_API_KEY", "ADK_BRIDGE_SECRET", "LAYA_INTERNAL_TOKEN", "DATABASE_URL",
           "OPERATOR_DATABASE_URL", "BACKOFFICE_DATABASE_URL", "TICKET_DATABASE_URL", "ADMIN_PASSWORD_HASH"}
PORTS = {"go": 8080, "adk": 8001, "laya": 8003}
ENV_KEYS = {
    "go": {"DATABASE_URL", "BACKOFFICE_DATABASE_URL", "PUBLIC_ORIGIN", "ADMIN_PASSWORD_HASH", "STATIC_DIR",
           "SHOPPER_AUTH_ENABLED", "SHOPPER_ACCOUNTS_FILE", "PORT", "READINESS_MODE", "VOICE_ENABLED", "VOICE_ALLOW_LOCAL_HTTP", "TICKET_DATABASE_URL", "ADK_BRIDGE_SECRET"},
    "adk": {"GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_VOICE", "ADK_BRIDGE_SECRET", "LAYA_INTERNAL_TOKEN"},
    "laya": {"LAYA_MODEL_PATH", "LAYA_INTERNAL_TOKEN"},
}


def base_env():
    return {k: v for k, v in os.environ.items() if k not in SECRETS | {"GOROOT"}}


def run(*args):
    subprocess.run(["rtk", "proxy", *map(str, args)], cwd=ROOT, env=base_env(), check=True)


def health(name):
    path = "/readyz" if name == "go" else "/healthz"
    try:
        with urlopen(f"http://127.0.0.1:{PORTS[name]}{path}", timeout=2) as response:
            return response.status == 200 and (name != "go" or response.headers.get("X-Readiness-Scope") == "full")
    except OSError:
        return False


def stop():
    for name in ("go", "adk", "laya"):
        file = RUN / f"{name}.pid"
        if not file.exists():
            continue
        pid = int(file.read_text().strip())
        command = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
        marker = {"go": str(ROOT / "bin/prompt-shop"), "adk": "uvicorn prompt_shop_live.app:app",
                  "laya": "uvicorn intent_service.app:app"}[name]
        owned = str(ROOT) in command and marker in command or name == "go" and command.strip().startswith("/tmp/prompt-shop-mvp-server")
        if command and not owned:
            raise RuntimeError("A saved PID belongs to another process; it was preserved")
        if command:
            os.kill(pid, signal.SIGTERM)
            for _ in range(100):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(.1)
            else:
                # Only a verified task-owned process can reach this bounded cleanup.
                os.kill(pid, signal.SIGKILL)
        file.unlink(missing_ok=True)


def service_env(name, values, module_path=None):
    env = base_env()
    env.update({k: v for k, v in values.items() if k in ENV_KEYS[name] and v is not None})
    if module_path:
        env["PYTHONPATH"] = str(module_path)
    return env


def launch(name, command, values, module_path=None):
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORTS[name])) == 0:
            raise RuntimeError(f"Port {PORTS[name]} is occupied; the existing service was preserved")
    env = service_env(name, values, module_path)
    with (RUN / f"{name}.log").open("wb") as log:
        process = subprocess.Popen(list(map(str, command)), cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (RUN / f"{name}.pid").write_text(str(process.pid) + "\n")
    for _ in range(90):
        if process.poll() is not None:
            raise RuntimeError(f"{name} exited; inspect tmp/run/{name}.log")
        if health(name):
            print(f"{name}: ready", flush=True)
            return
        time.sleep(1)
    raise RuntimeError(f"{name} startup timed out; inspect tmp/run/{name}.log")


def configure():
    agent_file = ROOT / "agent/.env"
    agent = dotenv_values(agent_file)
    if not agent.get("GOOGLE_API_KEY"):
        raise RuntimeError("Set GOOGLE_API_KEY in agent/.env before starting voice")
    file = ROOT / ".env"
    if not file.exists():
        file.write_bytes((ROOT / ".env.example").read_bytes())
    file.chmod(0o600)
    values = dotenv_values(file)
    if values.get("PORT", "8080") != "8080":
        raise RuntimeError("This local MVP launcher requires PORT=8080")
    origin = values.get("PUBLIC_ORIGIN") or "http://localhost:8080"
    if origin != "http://localhost:8080":
        raise RuntimeError("This local MVP launcher requires PUBLIC_ORIGIN=http://localhost:8080")
    bridge = agent.get("ADK_BRIDGE_SECRET") or ""
    if len(bridge) < 32:
        bridge = secrets.token_urlsafe(32)
    token = agent.get("LAYA_INTERNAL_TOKEN") or secrets.token_urlsafe(32)
    for key, value in {"ADK_BRIDGE_SECRET": bridge, "LAYA_INTERNAL_TOKEN": token}.items():
        set_key(agent_file, key, value)
    agent_file.chmod(0o600)
    database = quote(values.get("POSTGRES_DB") or "prompt_shop", safe="")
    port = int(values.get("POSTGRES_PORT") or "55432")
    ticket = values.get("TICKET_DATABASE_URL") or f"postgres://prompt_shop_ticket:local-ticket-only@127.0.0.1:{port}/{database}?sslmode=disable"
    if urlsplit(ticket).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("The local MVP launcher requires a loopback ticket database")
    for key, value in {"ADK_BRIDGE_SECRET": bridge, "VOICE_ENABLED": "true", "VOICE_ALLOW_LOCAL_HTTP": "true",
                       "PUBLIC_ORIGIN": origin, "READINESS_MODE": "full", "TICKET_DATABASE_URL": ticket}.items():
        set_key(file, key, value)
    intent_file = ROOT / "intent/local/.env"
    model = dotenv_values(intent_file).get("LAYA_MODEL_PATH")
    if not model:
        model = ROOT / "intent/local/model-bundle"
        if not model.exists():
            model = ROOT / ".worktrees/TASK-0010/intent/local/model-bundle"
    model = Path(model)
    if not model.is_absolute():
        model = ROOT / "intent" / model
    model = model.resolve()
    if not (model / "model.safetensors").is_file():
        raise RuntimeError("Prepare the pinned Laya bundle using intent/README.md; no model is downloaded at startup")
    intent_file.parent.mkdir(parents=True, exist_ok=True)
    intent_file.touch(mode=0o600, exist_ok=True)
    set_key(intent_file, "LAYA_MODEL_PATH", str(model))
    set_key(intent_file, "LAYA_INTERNAL_TOKEN", token)
    intent_file.chmod(0o600)
    if (values.get("SHOPPER_AUTH_ENABLED") or "true").lower() == "true":
        account_path = values.get("SHOPPER_ACCOUNTS_FILE")
        if not account_path:
            account_dir = ROOT / "tmp/auth"
            run("go", "run", "./cmd/demo-accounts", account_dir)
            account_path = str(account_dir / "accounts.json")
        if not values.get("BACKOFFICE_DATABASE_URL"):
            set_key(file, "BACKOFFICE_DATABASE_URL", f"postgres://prompt_shop_admin:local-admin-only@127.0.0.1:{port}/{database}?sslmode=disable")
        set_key(file, "SHOPPER_AUTH_ENABLED", "true")
        set_key(file, "SHOPPER_ACCOUNTS_FILE", account_path)
    return dotenv_values(file), dotenv_values(agent_file), dotenv_values(intent_file)


def start():
    if all(health(name) for name in PORTS) and all((RUN / f"{name}.pid").exists() for name in PORTS):
        print("MVP already running; use make mvp-restart to apply code/configuration changes")
        return
    values, agent, intent = configure()
    stop()
    run("make", "start")
    run("uv", "sync", "--project", "intent", "--frozen", "--python", "3.11")
    run("python3", "deploy/verify_model.py", intent["LAYA_MODEL_PATH"])
    run("npm", "--prefix", "web", "ci")
    run("npm", "--prefix", "web", "run", "build")
    binary = ROOT / "bin/prompt-shop"
    binary.parent.mkdir(exist_ok=True)
    run("go", "build", "-o", binary, "./cmd/server")
    launch("laya", [ROOT / "intent/.venv/bin/python", "-m", "uvicorn", "intent_service.app:app",
        "--app-dir", ROOT / "intent", "--host", "127.0.0.1", "--port", "8003", "--workers", "1",
        "--no-access-log", "--timeout-graceful-shutdown", "7"], intent, ROOT / "intent")
    launch("adk", [sys.executable, "-m", "uvicorn", "prompt_shop_live.app:app", "--app-dir", ROOT / "agent",
        "--host", "127.0.0.1", "--port", "8001", "--no-access-log", "--ws-max-size", "65536",
        "--ws-max-queue", "1", "--timeout-graceful-shutdown", "7"], agent, ROOT / "agent")
    launch("go", [binary], values)
    print("Open http://localhost:8080. Sign in for Monti’s welcome; choose Start voice to use your microphone. Logs: tmp/run/.")


def main():
    if os.environ.get("K_SERVICE"):
        raise RuntimeError("This launcher is local-only")
    RUN.mkdir(parents=True, exist_ok=True)
    RUN.chmod(0o700)
    action = sys.argv[1]
    if action == "mvp-status":
        for name in PORTS:
            print(f"{name}: {'ready' if health(name) else 'unavailable'}")
    elif action == "mvp-stop":
        stop()
        print("MVP application services stopped; PostgreSQL data and service retained")
    elif action in {"mvp-start", "mvp-restart"}:
        if action == "mvp-restart":
            stop()
        start()
    else:
        raise RuntimeError("Unknown MVP action")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        # Configuration errors are fixed messages; child stderr is never echoed with environment values.
        print(f"MVP startup stopped: {error}", file=sys.stderr)
        sys.exit(1)
