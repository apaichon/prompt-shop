"""Verify TASK-0010's predownloaded, offline English model bundle."""
import hashlib
import json
from pathlib import Path
import re
import sys


def verify(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("repository") != "convaiinnovations/laya":
        raise ValueError("only the English Laya repository is permitted")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("revision", "")):
        raise ValueError("model revision must be a full repository commit")
    if manifest.get("license") != "Apache-2.0":
        raise ValueError("expected recorded Apache-2.0 provenance")
    files = manifest.get("files", {})
    if not files or "LICENSE" not in files:
        raise ValueError("model hashes and LICENSE are required")
    if not any(n.endswith((".safetensors", ".bin", ".pt")) for n in files):
        raise ValueError("model weights are missing")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("model bundle cannot contain symlinks")
        if path.is_file() and path != root / "manifest.json":
            actual.add(path.relative_to(root).as_posix())
    if actual != set(files):
        raise ValueError("model bundle must match the manifest exactly")
    for name, digest in files.items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("model file escaped the bundle")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid model SHA256")
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        if sha != digest:
            raise ValueError("model checksum mismatch")
    return manifest


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]))
    except (ValueError, OSError, KeyError, TypeError) as error:
        sys.exit(f"model verification failed: {error}")
    print("English model bundle checksums verified; inference is a separate gate")
