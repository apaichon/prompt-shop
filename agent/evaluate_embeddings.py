"""Opt-in real embedding probe. Reports IDs/scores/timings, never text or keys."""
import argparse
import asyncio
import json
import math
import os
import time
from pathlib import Path

from tools.embedding_router import PREFIX, LABELS, default_router, decide

async def evaluate():
    router = default_router()
    try:
        await router.warm()
        cases = json.loads(Path(__file__).with_name("tools").joinpath("prototypes/embedding-eval-v1.json").read_text())["cases"]
        rows = []
        latencies = []
        for case in cases:
            # Stress all labels with existing results and route, including a new search.
            started = time.perf_counter()
            vector = (await router.embedder([PREFIX + case["text"]]))[0]
            result = decide(vector, router.prototypes, router.vectors, set(LABELS), router.revision)
            latency = round((time.perf_counter()-started)*1000)
            latencies.append(latency)
            correct = result["intent"] == case["expected_intent"]
            safe_no_tool = case["expected_intent"] == "out_of_scope" and result["abstained"]
            rows.append({"id":case["id"],"expected":case["expected_intent"],"actual":result["intent"],
                         "confidence":result["confidence"],"margin":result["margin"],
                         "latency_ms":latency,"tool_family_correct":correct or safe_no_tool})
        return {"model_revision":router.revision,"context":"all labels eligible",
                "exact_labels":sum(row["actual"]==row["expected"] for row in rows),
                "tool_families":sum(row["tool_family_correct"] for row in rows),"total":len(rows),
                "warm_p95_ms":sorted(latencies)[math.ceil(.95*len(latencies))-1],"cases":rows}
    finally:
        await router.embedder.aclose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true",help="Explicitly call the configured real Gemini API")
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if not args.live or not os.environ.get("GOOGLE_API_KEY"):
        parser.error("--live and GOOGLE_API_KEY are required")
    report = asyncio.run(evaluate())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"}))
