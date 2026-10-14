import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from .audit import audit_fixture, write_json
from .collector import collect_catalog, collect_routes, collect_anonymous
from .contracts import load_frozen
from .http import Client
from .report import template, release_report, measured_evidence


def main():
    parser = argparse.ArgumentParser(description="Task 6 acceptance: fixed corpora, isolated probes, explicit release blockers")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("audit", "template", "measure", "report", "http"):
        command = commands.add_parser(name)
        command.add_argument("--out", type=Path, required=True)
        if name in ("measure", "report"):
            command.add_argument("--observations", type=Path, required=True)
        if name == "report":
            command.add_argument("--http-run", type=Path)
            command.add_argument("--artifacts", type=Path)
        if name == "http":
            command.add_argument("--url", required=True)
            command.add_argument("--suite", choices=("all", "catalog", "routes", "anonymous"), default="all")
            command.add_argument("--local", action="store_true")
            command.add_argument("--insecure-local-tls", action="store_true")
            command.add_argument("--pace", type=float, default=1.05)
            command.add_argument("--candidate-commit")
            command.add_argument("--deployment-id")
    args = parser.parse_args()
    try:
        freeze, catalog, queries, intents = load_frozen()
        if args.command == "audit":
            result = audit_fixture(catalog, queries)
            passed = result["status"] == "pass"
        elif args.command == "template":
            result, passed = template(freeze), True
        elif args.command in ("measure", "report"):
            observations = json.loads(args.observations.read_text())
            if args.command == "measure":
                result = measured_evidence(observations, queries, intents)
                passed = all(r["status"] == "pass" for r in result.values())
            else:
                http_run = json.loads(args.http_run.read_text()) if args.http_run else None
                result = release_report(freeze, catalog, queries, intents, observations, http_run, args.artifacts)
                passed = result["recommendation"] == "READY_FOR_OWNER_REVIEW"
        else:
            client = Client(args.url, local=args.local, insecure_tls=args.insecure_local_tls, pace=args.pace)
            suites = {}
            for name, run in (("catalog", lambda: collect_catalog(client, catalog, queries)), ("routes", lambda: collect_routes(client, catalog)), ("anonymous", lambda: collect_anonymous(client))):
                if args.suite in ("all", name):
                    suites[name] = run()
            result = {"schema_version": "qa-http-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
                      "environment": client.environment, "origin": client.origin, "candidate_commit": args.candidate_commit,
                      "deployment_id": args.deployment_id, "frozen_inputs": freeze["files"], "suites": suites}
            passed = all(s["status"] == "pass" for s in suites.values())
        write_json(args.out, result)
        print(json.dumps({"output": str(args.out), "status": "pass" if passed else "blocked_or_failed"}))
        return 0 if passed else 1
    except (ValueError, KeyError, TypeError, IndexError, OSError):
        # Fixed error label, never raw supplied inputs, HTTP bodies, keys or exceptions.
        print("qa_error: invalid input or unavailable file", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
