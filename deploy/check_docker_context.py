"""Exercise the actual .dockerignore with synthetic inputs and a scratch image.

No network/base image or real secrets. Cleans up only its uniquely named image
and container. This verifies packaging, not application container readiness.
"""
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import uuid


def main():
    tag = "prompt-shop-context-test:" + uuid.uuid4().hex
    container = None
    def run(*args):
        return subprocess.run(["docker", *args], check=True, capture_output=True, timeout=90).stdout
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy2(Path(__file__).resolve().parent.parent / ".dockerignore", root / ".dockerignore")
            (root / "Dockerfile").write_text('FROM scratch\nCOPY . /\nCMD ["/not-executed"]\n')
            kept = ["go.mod", "cmd/server/main.go", "web/package.json", "web/src/app.html",
                    "agent/uv.lock", "agent/prompt_shop_live/app.py", "intent/model/model.safetensors",
                    "deploy/verify_model.py", "data/demo-store.json"]
            denied = ["agent/.env", "web/.env.production", "intent/credentials.json", "agent/.venv/x",
                      "web/node_modules/x", "agent/tests/test_x.py", "recordings/voice.wav",
                      "references/monti-jarvis/source", ".git/config", "deploy/local/staging.json"]
            for name in kept + denied:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic packaging fixture")
            run("build", "--tag", tag, str(root))
            container = run("create", tag).decode().strip()
            with tarfile.open(fileobj=io.BytesIO(run("export", container))) as archive:
                names = {member.name for member in archive.getmembers()}
            missing = set(kept) - names
            leaked = set(denied) & names
            if missing or leaked:
                raise ValueError(f"Docker context mismatch: missing={sorted(missing)}, leaked={sorted(leaked)}")
            print("Docker context check passed: production inputs included; synthetic private/generated inputs excluded")
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=20)
        subprocess.run(["docker", "image", "rm", tag], capture_output=True, timeout=20)


if __name__ == "__main__":
    main()
