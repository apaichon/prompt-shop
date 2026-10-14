"""Limited real-image resource probe; not the 40-case or GCP acceptance gate.

Run with the locked agent Python environment. Never overwrites existing evidence,
containers or an occupied private port. No credential or input content is logged.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"agent"))
import httpx
from tools.intent import Classifier, MODEL_REVISION

NAME = "prompt-shop-task10-resource-probe"


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=40)


async def run(image, output):
    if output.exists(): raise ValueError("use a new evidence path")
    with socket.socket() as probe: probe.bind(("127.0.0.1", 8003))
    if docker("container", "inspect", NAME).returncode == 0:
        raise ValueError("task probe container already exists")
    inspection = docker("image", "inspect", image)
    if inspection.returncode: raise ValueError("image not available locally")
    facts = json.loads(inspection.stdout)[0]
    image_id = facts["Id"]
    token = secrets.token_urlsafe(40)
    started = time.monotonic()
    report = {"schema_version": "laya-container-probe-v1", "started_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Actual Task 5 Dockerfile, verified English weights and CPU-only Linux wheel; 2 CPU/4 GiB local Docker quota. AMD64 image on ARM host is emulated. Three probes at most; no 30-sample or GCP acceptance claim.",
              "host_architecture": platform.machine(), "image_id": image_id, "image_architecture": facts["Architecture"],
              "limits": {"cpus": 2, "memory_bytes": 4294967296, "pids": 128}, "model_revision": MODEL_REVISION,
              "probes": [], "deployed_acceptance": False}
    owned = False
    local = ROOT/"intent/local"
    local.mkdir(exist_ok=True)
    handle = tempfile.NamedTemporaryFile(dir=local, mode="w", prefix="container-token-", delete=False)
    try:
        os.chmod(handle.name, 0o600)
        handle.write("LAYA_INTERNAL_TOKEN="+token+"\n")
        handle.close()
        result = docker("run", "--detach", "--name", NAME, "--platform=linux/amd64", "--cpus=2", "--memory=4g", "--pids-limit=128",
                        "--publish", "127.0.0.1:8003:8003", "--env-file", handle.name, image_id)
        if result.returncode: raise ValueError("container start failed")
        owned = True
        status = None
        async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
            while time.monotonic()-started < 180:
                try:
                    response = await client.get("http://127.0.0.1:8003/healthz")
                    if response.status_code == 200:
                        status = response.json(); break
                except httpx.HTTPError: pass
                await asyncio.sleep(.2)
            report["ready"] = status is not None
            report["cold_ready_ms"] = (time.monotonic()-started)*1000
            report["model_load"] = status.get("load") if status else None
            if status and status.get("model_revision") != MODEL_REVISION:
                raise ValueError("checkpoint identity differs")
            if status:
                unauthorized = await client.post("http://127.0.0.1:8003/classify", json={"text": "Synthetic resource probe"})
                report["unauthorized_http_status"] = unauthorized.status_code
                classifier = Classifier(token)
                for index in range(3):
                    clock = time.monotonic()
                    value = await classifier("A shopper asks to locate a store product.")
                    report["probes"].append({"id": index+1, "elapsed_ms": (time.monotonic()-clock)*1000, "result": value})
                    if value["reason"] in ("timeout", "busy", "error"): break
        code = 'import json,pathlib,platform,importlib.metadata; p=pathlib.Path("/sys/fs/cgroup"); print(json.dumps({"machine":platform.machine(),"torch":importlib.metadata.version("torch"),"cgroup":{n:(p/n).read_text().strip() for n in ("cpu.max","memory.max","memory.peak","pids.max") if (p/n).exists()}}))'
        result = docker("exec", NAME, "/app/intent/.venv/bin/python", "-c", code)
        report["runtime"] = json.loads(result.stdout) if result.returncode == 0 else None
        inspect = docker("container", "inspect", NAME)
        if inspect.returncode == 0:
            state = json.loads(inspect.stdout)[0]
            report["container_state"] = {k: state["State"][k] for k in ("Running", "OOMKilled", "ExitCode")}
            report["configured_limits"] = {k: state["HostConfig"][k] for k in ("NanoCpus", "Memory", "PidsLimit")}
        report["limited_probe_result"] = "pass" if report["ready"] and len(report["probes"]) == 3 and all(x["result"]["reason"] not in ("timeout", "busy", "error") for x in report["probes"]) else "fail"
    finally:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)
        if owned:
            stop = docker("stop", "--time", "10", NAME)
            remove = docker("rm", NAME)
            report["owned_container_cleanup"] = stop.returncode == remove.returncode == 0
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"result": report["limited_probe_result"], "ready": report["ready"], "output": str(output)}))
    return 0 if report["limited_probe_result"] == "pass" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.image, args.out)))
