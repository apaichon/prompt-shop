"""Actual pinned model via private HTTP and the real ADK BlockingTool, no Gemini key.

Frozen inputs/scores are never tuned here. Only IDs/results/timings are recorded.
Creates a task-owned local service only when port 8003 is free, then shuts it down.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"agent"))
from tools.intent import Classifier, MODEL_REVISION
from prompt_shop_live.host import ToolHost
from prompt_shop_live.protocol import Setup
from prompt_shop_live.tools import BlockingTool


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values):
    sorted_values=sorted(values)
    return {"samples":len(values),"p50_ms":sorted_values[(len(values)-1)//2],"p95_ms":sorted_values[__import__('math').ceil(.95*len(values))-1],"max_ms":max(values)}


async def evaluate(model, output, service_python):
    output=Path(output)
    if output.exists(): raise ValueError("use a new evidence path")
    freeze=json.loads((ROOT/"intent/evaluation/freeze.json").read_text())
    for name,key in [("intent/evaluation/corpus.json","corpus_sha256"),("intent/config/intent-v1.json","config_sha256")]:
        if sha(ROOT/name)!=freeze[key]: raise ValueError("frozen evaluation input changed")
    if json.loads((ROOT/"intent/model/manifest.json").read_text())["revision"]!=freeze["model_revision"]:
        raise ValueError("frozen checkpoint changed")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",8003))  # Fails if another service owns the fixed private port.
    token=secrets.token_urlsafe(40)
    env=dict(os.environ,LAYA_INTERNAL_TOKEN=token,LAYA_MODEL_PATH=str(Path(model).resolve()),HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_TELEMETRY="1",TOKENIZERS_PARALLELISM="false",OMP_NUM_THREADS="2",USE_TF="0")
    started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    process=subprocess.Popen([str(service_python),"-m","uvicorn","intent_service.app:app","--host","127.0.0.1","--port","8003","--no-access-log","--log-level","critical","--workers","1","--timeout-graceful-shutdown","7"],cwd=ROOT/"intent",env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    observations,warm,events,heartbeats=[],[],[],[]
    host=None;running=True
    async def heartbeat():
        while running:
            heartbeats.append(time.monotonic());await asyncio.sleep(.005)
    beat=asyncio.create_task(heartbeat())
    try:
        async with httpx.AsyncClient(trust_env=False,timeout=1) as client:
            status=None
            while time.monotonic()-clock<120 and process.poll() is None:
                try:
                    response=await client.get("http://127.0.0.1:8003/healthz")
                    if response.status_code==200:
                        status=response.json();break
                except httpx.HTTPError: pass
                await asyncio.sleep(.1)
            if status is None or status.get("model_revision")!=MODEL_REVISION:
                raise ValueError("actual model failed to warm")
        cold_ms=(time.monotonic()-clock)*1000
        async def send(event):
            events.append({"type":event["type"],"result":event.get("result")})
            host.acknowledge(event)  # Isolated Go bridge ACK fixture, actual classifier is not mocked.
        async def callback(request):
            raise AssertionError("classification corpus must not call a catalog/admin tool")
        async with httpx.AsyncClient(transport=httpx.MockTransport(callback)) as go:
            host=ToolHost(Setup(type="setup",session_id="task10-isolated",language="en-US",turn_id="turn-0",tool_capability=secrets.token_urlsafe(32)),send,Classifier(token),go)
            tool=BlockingTool("classify_intent",host)
            declaration=tool._get_declaration()
            if declaration.behavior.value!="BLOCKING": raise ValueError("actual ADK tool is not blocking")
            corpus=json.loads((ROOT/"intent/evaluation/corpus.json").read_text())
            for index,case in enumerate(corpus,1):
                host.begin("turn-"+str(index));start=time.monotonic()
                value=await tool.run_async(args={"text":case["text"]},tool_context=None)
                duration=(time.monotonic()-start)*1000
                observations.append({"id":case["id"],"expected":case["expected_intent"],"result":value,"elapsed_ms":duration,"classification_acknowledged":host.classified})
                print(json.dumps({"case":index,"correct":value.get("intent")==case["expected_intent"] and not value.get("abstained",True),"abstained":value.get("abstained",True),"elapsed_ms":round(duration,2)}),flush=True)
            for index in range(30):
                host.begin("turn-"+str(41+index));start=time.monotonic()
                value=await tool.run_async(args={"text":"A shopper asks to locate a store product."},tool_context=None)
                warm.append({"id":index+1,"elapsed_ms":(time.monotonic()-start)*1000,"result":value})
            await host.close()
        labels=["find_item","select_item","repeat_directions","out_of_scope"]
        matrix={label:{actual:0 for actual in labels+["abstained_or_error"]} for label in labels}
        correct=covered=0
        for row in observations:
            value=row["result"];actual=value.get("intent") if value.get("abstained") is False else "abstained_or_error"
            if actual not in labels: actual="abstained_or_error"
            matrix[row["expected"]][actual]+=1;covered+=actual in labels;correct+=actual==row["expected"]
        warm_summary=summary([row["elapsed_ms"] for row in warm])
        runtime=status["load"]["runtime"]
        passed=correct>=36 and all(row["classification_acknowledged"] for row in observations) and warm_summary["p95_ms"]<=1200 and all(row["result"].get("reason") not in ("timeout","busy","error") for row in warm)
        report={"schema_version":"laya-evaluation-v1","started_at":started,"completed_at":datetime.now(timezone.utc).isoformat(),"scope":"Actual pinned CPU English Laya through private HTTP and real ADK BlockingTool. Only the Go ACK/catalog bridge is an isolated fixture. No native Gemini/deployed voice claim.","environment":{"system":platform.system(),"machine":platform.machine(),"cpu_count":os.cpu_count(),"deployment_cpu_ram_qualified":False},"model_revision":MODEL_REVISION,"frozen":freeze,"manifest_sha256":sha(ROOT/"intent/model/manifest.json"),"package_lock_sha256":sha(ROOT/"intent/uv.lock"),"adk_lock_sha256":sha(ROOT/"agent/uv.lock"),"adk_version":__import__('importlib.metadata',fromlist=['version']).version('google-adk'),"tool_behavior":declaration.behavior.value,"cold_service_ready_ms":cold_ms,"model_load":status["load"],"correct":correct,"total":40,"coverage":covered/40,"per_class_accuracy":{label:matrix[label][label]/10 for label in labels},"confusion":matrix,"observations":observations,"warm_samples":warm,"warm_summary":warm_summary,"heartbeat_max_gap_ms":max(b-a for a,b in zip(heartbeats,heartbeats[1:]))*1000,"normal_inference_gate":"pass" if passed else "fail","full_test0012_status":"pending fault/private/advisory/resource evidence review; host measurements cannot establish GCP qualification","implementation_hashes":{name:sha(ROOT/name) for name in ["intent/intent_service/model.py","intent/intent_service/protocol.py","intent/intent_service/app.py","intent/intent_service/worker.py","agent/tools/intent.py"]}}
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
        print(json.dumps({"correct":correct,"total":40,"warm_p95_ms":warm_summary["p95_ms"],"gate":report["normal_inference_gate"],"output":str(output)}),flush=True)
        return 0 if passed else 1
    finally:
        running=False;await beat
        if host is not None: await host.close()
        if process.poll() is None:
            process.terminate()
            try: await asyncio.to_thread(process.wait,10)
            except subprocess.TimeoutExpired:
                process.kill();await asyncio.to_thread(process.wait,2)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--service-python",type=Path,default=ROOT/"intent/.venv/bin/python")
    args=parser.parse_args()
    try: raise SystemExit(asyncio.run(evaluate(args.model,args.out,args.service_python)))
    except (ValueError,OSError,httpx.HTTPError):
        print("evaluation_blocked: invalid frozen inputs, port conflict or model/runtime unavailability",file=sys.stderr);raise SystemExit(2)
