"""Package a committed integration tree and optionally build all three images.

No push, credentials, cloud calls, or implicit dependency merges. Output lives
outside the checkout; every runtime image uses the same source commit.
"""
import argparse
import fnmatch
import io
import json
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys
import tarfile

from staging import require, validate_lock
from verify_model import verify

REQUIRED = ["Dockerfile", ".dockerignore", "go.mod", "go.sum", "cmd/server/main.go",
            "cmd/import/main.go", "data/demo-store.json", "web/package.json", "web/package-lock.json",
            "agent/Dockerfile", "agent/pyproject.toml", "agent/uv.lock", "agent/prompt_shop_live/app.py",
            "agent/tools/intent.py", "intent/Dockerfile", "intent/pyproject.toml", "intent/uv.lock",
            "intent/intent_service/app.py", "intent/model/manifest.json", "deploy/verify_model.py"]
ROOT_FILES = {"Dockerfile", ".dockerignore", "go.mod", "go.sum", "data/demo-store.json", "deploy/verify_model.py"}
SOURCE_DIRS = {"cmd", "internal", "migrations", "web", "agent", "intent"}
EXCLUDED_DIRS = {"node_modules", ".svelte-kit", "build", ".venv", "__pycache__", ".pytest_cache", "tests", "recordings"}


def allowed(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if name not in ROOT_FILES and (len(path.parts) < 2 or path.parts[0] not in SOURCE_DIRS):
        return False
    if set(path.parts) & EXCLUDED_DIRS:
        return False
    patterns = [".env*", "*credentials*", "*.pem", "*.key", "*.wav", "*.mp3", "*.pcm",
                "*.test.*", "*_test.go", "*.log", ".DS_Store"]
    return not any(fnmatch.fnmatch(part.lower(), pattern) for part in path.parts for pattern in patterns)


def package(root, commit, destination, model_bundle=None):
    require(not destination.exists(), "context destination must not exist")
    result = subprocess.run(["git", "-C", str(root), "archive", "--format=tar", commit], check=True, capture_output=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        members = [member for member in archive.getmembers() if allowed(member.name) and not member.isdir()]
        require(all(member.isfile() for member in members), "source symlinks/devices are forbidden in build context")
        names = {member.name for member in members}
        missing = sorted(set(REQUIRED) - names)
        require(not missing, "integration build inputs missing: " + ", ".join(missing))
        destination.mkdir(parents=True)
        for member in members:
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    model = destination / "intent/model"
    if model_bundle is not None:
        verify(model_bundle)
        require(json.loads((model / "manifest.json").read_text()) ==
                json.loads((model_bundle / "manifest.json").read_text()),
                "external model bundle differs from committed manifest")
        shutil.copytree(model_bundle, model, dirs_exist_ok=True)
    verify(model)


def commands(lock, context, registry):
    import re
    require(re.fullmatch(r"[a-z]+-[a-z]+[0-9]-docker.pkg.dev/[a-z][a-z0-9-]+/[a-z][a-z0-9-]+", registry), "use a regional Artifact Registry repository")
    for name, dockerfile in [("go", "Dockerfile"), ("adk", "agent/Dockerfile"), ("laya", "intent/Dockerfile")]:
        args = ["docker", "build", "--platform=linux/amd64", "--pull", "--file", str(context / dockerfile),
                "--label", "org.opencontainers.image.revision=" + lock["source_commit"],
                "--tag", registry + "/" + name + ":" + lock["source_commit"]]
        for key, value in sorted(lock["bases"].items()):
            args.extend(["--build-arg", key + "=" + value])
        yield args + [str(context)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--model-bundle", type=Path, help="preverified weights matching the committed manifest")
    parser.add_argument("--execute", action="store_true", help="build locally; never pushes")
    args = parser.parse_args()
    lock = json.loads(args.images.read_text())
    validate_lock(lock)
    context = args.context.resolve()
    require(not context.is_relative_to(args.root.resolve()), "build context must be outside the checkout")
    plan = list(commands(lock, context, args.registry))
    package(args.root, lock["source_commit"], context, args.model_bundle)
    for command in plan:
        if args.execute:
            subprocess.run(command, check=True)
        else:
            print("rtk proxy " + shlex.join(command))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        sys.exit(f"build rejected: {error}")
