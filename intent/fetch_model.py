"""Download the fixed reviewed English bundle before deployment; no credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

REPOSITORY = "convaiinnovations/laya"
REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"
WEIGHTS_SHA256 = "891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c"
FILES = ("rl_agent_config.json", "config.json", "encoder/config.json", "tokenizer/tokenizer.json", "tokenizer/tokenizer_config.json", "model.safetensors", "README.md")


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".partial")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, pending.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024*1024)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.stat().st_size < 10_000_000 else file_hash(path)


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(destination, license_commit):
    if destination.exists():
        raise ValueError("use an absent destination; never overwrite a model bundle")
    destination.mkdir(parents=True)
    hashes = {}
    for name in FILES:
        value = download(f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}", destination/name)
        if name == "model.safetensors" and value != WEIGHTS_SHA256:
            raise ValueError("weight checksum differs from publisher metadata")
        hashes[name] = value
        print(json.dumps({"file": name, "bytes": (destination/name).stat().st_size, "sha256": value}), flush=True)
    if "license: apache-2.0" not in (destination/"README.md").read_text().lower():
        raise ValueError("pinned model card license differs")
    url = f"https://raw.githubusercontent.com/NandhaKishorM/laya/{license_commit}/LICENSE"
    hashes["LICENSE"] = download(url, destination/"LICENSE")
    provenance = {"model_card": f"https://huggingface.co/{REPOSITORY}/blob/{REVISION}/README.md", "license_text_source": url,
                  "note": "Model repository declares Apache-2.0 in its pinned card; root has no LICENSE. Full Apache-2.0 notice is retained from the pinned publisher package source. No remote model Python code is executed."}
    (destination/"PROVENANCE.json").write_text(json.dumps(provenance, indent=2)+"\n")
    hashes["PROVENANCE.json"] = file_hash(destination/"PROVENANCE.json")
    manifest = {"repository": REPOSITORY, "revision": REVISION, "license": "Apache-2.0", "files": hashes}
    (destination/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--license-commit", required=True)
    args = parser.parse_args()
    import re
    if not re.fullmatch(r"[0-9a-f]{40}", args.license_commit):
        parser.error("full publisher source commit required")
    fetch(args.out, args.license_commit)
