"""Run the voice package in a disposable module until TASK-0001 integrates deps.

Copies only this owned package; never mutates another task's root go.mod/go.sum.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile

go = os.environ.get("PROMPT_SHOP_GO", "go")
root = pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="prompt-shop-voice-") as tmp:
    work = pathlib.Path(tmp)
    for path in root.glob("*.go"):
        shutil.copy2(path, work / path.name)
    shutil.copy2(root / "testdata/harness.mod", work / "go.mod")
    sums = root / "testdata/harness.sum"
    if sums.exists():
        shutil.copy2(sums, work / "go.sum")
    subprocess.run(["rtk", "proxy", go, "mod", "tidy"], cwd=work, check=True)
    if not sums.exists() or os.environ.get("VOICE_UPDATE_LOCK") == "1":
        shutil.copy2(work / "go.mod", root / "testdata/harness.mod")
        shutil.copy2(work / "go.sum", sums)
    elif (work / "go.mod").read_bytes() != (root / "testdata/harness.mod").read_bytes() or (work / "go.sum").read_bytes() != sums.read_bytes():
        raise RuntimeError("Harness dependency lock changed; review and update lock explicitly")
    subprocess.run(["rtk", "proxy", go, "vet", "./..."], cwd=work, check=True)
    subprocess.run(["rtk", "proxy", go, "test", "-race", "-count=1", "-v", "./..."], cwd=work, check=True)
