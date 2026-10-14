"""Verified local English weights, explicit CPU/eager backend and no downloads."""
import hashlib
import json
import os
from pathlib import Path

from .protocol import MODEL_REVISION, decision, valid_text

ROOT = Path(__file__).resolve().parent.parent


def verify_bundle(root):
    root = Path(root)
    expected = json.loads((ROOT/"model/manifest.json").read_text())
    actual = json.loads((root/"manifest.json").read_text())
    if actual != expected or actual.get("repository") != "convaiinnovations/laya" or actual.get("revision") != MODEL_REVISION or actual.get("license") != "Apache-2.0":
        raise ValueError("bundle differs from committed model pin")
    files = actual["files"]
    found = set()
    for file in root.rglob("*"):
        if file.is_symlink():
            raise ValueError("model bundle cannot contain symlinks")
        if file.is_file() and file != root/"manifest.json":
            found.add(file.relative_to(root).as_posix())
    if found != set(files):
        raise ValueError("model file inventory differs")
    for name, expected_hash in files.items():
        file = root/name
        if not file.resolve().is_relative_to(root.resolve()):
            raise ValueError("model path escaped bundle")
        with file.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected_hash:
                raise ValueError("model checksum differs")
    return actual


class EnglishModel:
    def __init__(self, root):
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false", USE_TF="0", OMP_NUM_THREADS="2")
        # Fail before native loading if any bundled byte or identity is unqualified.
        manifest = verify_bundle(root)
        config = json.loads((ROOT/"config/intent-v1.json").read_text())
        if config["confidence_min"] != .70 or config["margin_min"] != .15 or config["cpu_threads"] != 2:
            raise ValueError("frozen classifier thresholds differ")
        import torch
        from laya import Agent
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        self.agent = Agent(str(Path(root).resolve()), device="cpu", backend="eager", expected_sha256=manifest["files"])
        self.questions, self.max_len = config["questions"], config["max_len"]
        if self.agent.device.type != "cpu" or self.agent.backend != "eager":
            raise ValueError("CPU eager inference required")
        self.predict("A shopper asks to locate a store product.")  # Independent startup warm-up, outside the holdout.
        from importlib.metadata import version
        self.runtime = {"device": str(self.agent.device), "backend": self.agent.backend, "torch_threads": torch.get_num_threads(),
                        "packages": {name: version(name) for name in ("laya", "torch", "transformers", "huggingface-hub", "safetensors", "numpy")}}

    def predict(self, text):
        raw = self.agent.predict(valid_text(text), self.questions, max_len=self.max_len)
        usage = raw.get("usage", {})
        if usage.get("truncated") or usage.get("truncated_questions") or usage.get("options"):
            raise ValueError("model input/options truncated")
        return decision(raw)
