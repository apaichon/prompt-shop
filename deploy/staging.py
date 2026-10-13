"""Render reviewable Cloud Run manifests/provisioning commands; never runs gcloud.

Python 3.11+, standard library only. JSON output is valid YAML for gcloud replace.
No secret values belong in these inputs or outputs.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import shlex
import sys

SECRET_ENV = {
    "go": {"DATABASE_URL": "database", "BACKOFFICE_DATABASE_URL": "backoffice-database",
           "TICKET_DATABASE_URL": "ticket-database", "ADMIN_PASSWORD_HASH": "admin-password-hash",
           "ADK_BRIDGE_SECRET": "adk-bridge"},
    "adk": {"GOOGLE_API_KEY": "gemini-api-key", "ADK_BRIDGE_SECRET": "adk-bridge",
            "LAYA_INTERNAL_TOKEN": "laya-token"},
    "laya": {"LAYA_INTERNAL_TOKEN": "laya-token"},
    "operator": {"OPERATOR_DATABASE_URL": "operator-database"},
}
APIS = ["run", "artifactregistry", "secretmanager", "sqladmin", "iam", "logging",
        "monitoring", "billingbudgets", "cloudresourcemanager"]
BASE_KEYS = {"GO_IMAGE", "NODE_IMAGE", "RUNTIME_IMAGE", "PYTHON_IMAGE", "UV_IMAGE"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def validate_config(c, *, render=False):
    expected = set(json.loads((Path(__file__).parent / "staging.example.json").read_text()))
    require(set(c) == expected, "configuration keys must match staging.example.json; never add secret values")
    require(matches(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", c.get("project_id")), "project_id required")
    require(matches(r"[0-9]{6,}", c.get("project_number")), "project_number required")
    require(matches(r"[a-z]+-[a-z]+[0-9]", c.get("region")), "region required")
    for field in ("service", "repository", "sql_instance"):
        require(matches(r"[a-z][a-z0-9-]{2,39}", c.get(field)), f"invalid {field}")
    require(matches(r"[a-z][a-z0-9_]{1,40}", c.get("sql_database")), "invalid sql_database")
    require(c.get("sql_version") == "POSTGRES_16", "this plan targets PostgreSQL 16")
    require(matches(r"db-(custom-[0-9]+-[0-9]+|f1-micro|g1-small)", c.get("sql_tier")), "approved SQL tier required")
    require(type(c.get("sql_storage_gb")) is int and 10 <= c["sql_storage_gb"] <= 100, "SQL storage must be 10–100 GB")
    require(matches(r"[A-F0-9]{6}-[A-F0-9]{6}-[A-F0-9]{6}", c.get("billing_account")), "billing_account required")
    require(matches(r"[1-9][0-9]*(\.[0-9]{1,2})?[A-Z]{3}", c.get("budget_amount")), "budget_amount required, e.g. 25USD")
    require(matches(r"projects/[0-9]+/notificationChannels/[0-9]+", c.get("budget_notification_channel")), "verified email notification channel required")
    require(isinstance(c.get("approved_by"), str) and bool(c["approved_by"].strip()), "record cloud authorization in approved_by")
    require(date.fromisoformat(c.get("cleanup_date") or "1900-01-01") >= date.today(), "future cleanup/retention date required")
    require(c.get("reviewer_access") in ("private", "public"), "explicit reviewer_access required")
    expected = set().union(*(set(env.values()) for env in SECRET_ENV.values()))
    require(set(c.get("secrets", {})) == expected, "exact named secret inventory required")
    names = []
    for secret in c["secrets"].values():
        require(set(secret) == {"name", "version"}, "secret objects accept name/version only; never values")
        require(matches(r"[a-z][a-z0-9-]{2,100}", secret["name"]), "invalid secret name")
        names.append(secret["name"])
        if render:
            require(matches(r"[1-9][0-9]*", secret["version"]), "pin numeric secret versions, never latest")
    require(len(set(names)) == len(names), "secret roles must use distinct names")
    if render:
        require(matches(r"https://[a-z0-9][a-z0-9.-]+", c.get("public_origin")), "exact HTTPS origin required (no slash/path)")
        require(matches(r"[a-z][a-z0-9-]{0,14}[a-z0-9]", c.get("revision_suffix")), "revision_suffix required")
        previous = c.get("previous_revision")
        require(previous is None or matches(re.escape(c["service"]) + r"-[a-z0-9-]+", previous), "previous_revision must belong to this service")


def validate_lock(lock, c=None):
    require(set(lock) == {"source_commit", "images", "bases", "integration_evidence"}, "unexpected image lock fields")
    require(matches(r"[0-9a-f]{40}", lock.get("source_commit")), "source_commit must be a full git commit")
    require(set(lock.get("bases", {})) == BASE_KEYS, "all five base images required")
    for value in lock["bases"].values():
        require(matches(r"[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}", value), "base images require immutable digests")
    if c is not None:
        require(set(lock.get("images", {})) == {"go", "adk", "laya"}, "all three runtime images required")
        prefix = f'{c["region"]}-docker.pkg.dev/{c["project_id"]}/{c["repository"]}/'
        for name, value in lock["images"].items():
            require(matches(re.escape(prefix + name) + r"@sha256:[0-9a-f]{64}", value), "runtime digest must belong to the configured repository/image")
        require(isinstance(lock.get("integration_evidence"), str) and bool(lock["integration_evidence"].strip()), "record runtime contract/build qualification evidence")


def account(c, role):
    return f'prompt-shop-{role}@{c["project_id"]}.iam.gserviceaccount.com'


def connection(c):
    return f'{c["project_id"]}:{c["region"]}:{c["sql_instance"]}'


def secret_env(c, role):
    return [{"name": env, "valueFrom": {"secretKeyRef": {
        "name": c["secrets"][key]["name"], "key": c["secrets"][key]["version"]}}}
        for env, key in SECRET_ENV[role].items()]


def probe(port, path):
    return {"httpGet": {"path": path, "port": port}, "timeoutSeconds": 2,
            "periodSeconds": 5, "failureThreshold": 48}


def render(c, lock):
    validate_config(c, render=True)
    validate_lock(lock, c)
    containers = []
    for role, cpu, memory, port in [("go", "1", "512Mi", 8080), ("adk", "1", "512Mi", 8001), ("laya", "2", "4Gi", 8003)]:
        container = {"name": role, "image": lock["images"][role],
                     "resources": {"limits": {"cpu": cpu, "memory": memory}},
                     "env": secret_env(c, role),
                     "startupProbe": probe(port, "/readyz" if role == "go" else "/healthz")}
        # Only Go is an ingress container. Sidecar probe ports are private.
        if role == "go":
            container["ports"] = [{"name": "http1", "containerPort": port}]
            container["livenessProbe"] = {"httpGet": {"path": "/healthz", "port": port},
                                          "periodSeconds": 10, "timeoutSeconds": 2, "failureThreshold": 3}
            container["env"] += [{"name": k, "value": v} for k, v in {
                "READINESS_MODE": "full", "STATIC_DIR": "/app/web/build",
                "PUBLIC_ORIGIN": c["public_origin"], "VOICE_ENABLED": "true"}.items()]
        containers.append(container)
    revision = c["service"] + "-" + c["revision_suffix"]
    require(revision != c.get("previous_revision"), "candidate must differ from previous_revision")
    traffic = [{"revisionName": revision, "tag": "candidate", "percent": 0}]
    if c.get("previous_revision"):
        traffic.append({"revisionName": c["previous_revision"], "percent": 100})
    else:
        # First service has no known-good revision; explicitly a first staging deployment.
        traffic[0]["percent"] = 100
    service = {"apiVersion": "serving.knative.dev/v1", "kind": "Service",
               "metadata": {"name": c["service"], "namespace": c["project_number"],
                            "labels": {"cloud.googleapis.com/location": c["region"]},
                            "annotations": {"run.googleapis.com/ingress": "all",
                                            "run.googleapis.com/invoker-iam-disabled": "false"}},
               "spec": {"template": {"metadata": {"name": revision, "annotations": {
                   "autoscaling.knative.dev/minScale": "0", "autoscaling.knative.dev/maxScale": "2",
                   "run.googleapis.com/execution-environment": "gen2",
                   "run.googleapis.com/cpu-throttling": "true",
                   "run.googleapis.com/container-dependencies": json.dumps({"go": ["adk"], "adk": ["laya"]}),
                   "run.googleapis.com/cloudsql-instances": connection(c)}},
                   "spec": {"serviceAccountName": account(c, "runtime"), "containerConcurrency": 10,
                            "timeoutSeconds": 360, "containers": containers}}, "traffic": traffic}}
    job = {"apiVersion": "run.googleapis.com/v1", "kind": "Job",
           "metadata": {"name": c["service"] + "-import", "namespace": c["project_number"]},
           "spec": {"template": {"metadata": {"annotations": {"run.googleapis.com/cloudsql-instances": connection(c)}},
            "spec": {"parallelism": 1, "taskCount": 1, "template": {"spec": {
                "serviceAccountName": account(c, "operator"), "maxRetries": 0, "timeoutSeconds": 300,
                "containers": [{"name": "import", "image": lock["images"]["go"],
                    "command": ["/app/import"], "args": ["-migrate", "-file", "/app/data/demo-store.json"],
                    "env": secret_env(c, "operator"), "resources": {"limits": {"cpu": "1", "memory": "512Mi"}}}]}}}}}}
    return service, job


def provision_commands(c):
    validate_config(c)
    commands = []
    def add(*args):
        commands.append(["gcloud", *args, "--project=" + c["project_id"]])
    add("services", "enable", *(x + ".googleapis.com" for x in APIS))
    # Create the approved alert BEFORE creating paid resources. Alerts are not caps.
    add("billing", "budgets", "create", "--billing-account=" + c["billing_account"],
        "--display-name=prompt-shop-staging", "--budget-amount=" + c["budget_amount"],
        "--filter-projects=projects/" + c["project_number"], "--calendar-period=month",
        "--notifications-rule-monitoring-notification-channels=" + c["budget_notification_channel"],
        "--threshold-rule=percent=0.5", "--threshold-rule=percent=0.8", "--threshold-rule=percent=1.0")
    add("artifacts", "repositories", "create", c["repository"], "--repository-format=docker", "--location=" + c["region"])
    for role in ("runtime", "operator", "builder", "deployer"):
        add("iam", "service-accounts", "create", "prompt-shop-" + role)
    for role in ("runtime", "operator"):
        add("projects", "add-iam-policy-binding", c["project_id"],
            "--member=serviceAccount:" + account(c, role), "--role=roles/cloudsql.client", "--condition=None")
    for role, iam in (("builder", "roles/artifactregistry.writer"), ("deployer", "roles/artifactregistry.reader")):
        add("artifacts", "repositories", "add-iam-policy-binding", c["repository"], "--location=" + c["region"],
            "--member=serviceAccount:" + account(c, role), "--role=" + iam)
    add("projects", "add-iam-policy-binding", c["project_id"], "--member=serviceAccount:" + account(c, "deployer"),
        "--role=roles/run.developer", "--condition=None")
    for role in ("runtime", "operator"):
        add("iam", "service-accounts", "add-iam-policy-binding", account(c, role),
            "--member=serviceAccount:" + account(c, "deployer"), "--role=roles/iam.serviceAccountUser")
    for key, secret in c["secrets"].items():
        add("secrets", "create", secret["name"], "--replication-policy=user-managed", "--locations=" + c["region"])
        role = "operator" if key == "operator-database" else "runtime"
        add("secrets", "add-iam-policy-binding", secret["name"],
            "--member=serviceAccount:" + account(c, role), "--role=roles/secretmanager.secretAccessor")
    add("sql", "instances", "create", c["sql_instance"], "--database-version=" + c["sql_version"],
        "--edition=ENTERPRISE", "--tier=" + c["sql_tier"], "--region=" + c["region"],
        "--storage-size=" + str(c["sql_storage_gb"]), "--storage-type=SSD", "--no-storage-auto-increase",
        "--availability-type=zonal", "--assign-ip", "--connector-enforcement=REQUIRED",
        "--ssl-mode=ENCRYPTED_ONLY", "--backup-start-time=20:00", "--enable-point-in-time-recovery",
        "--deletion-protection", "--database-flags=log_statement=none,log_min_error_statement=panic,log_min_duration_statement=-1")
    add("sql", "databases", "create", c["sql_database"], "--instance=" + c["sql_instance"])
    return commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["provision-plan", "render"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--images", type=Path)
    parser.add_argument("--out", type=Path, default=Path("deploy/out"))
    args = parser.parse_args()
    c = json.loads(args.config.read_text())
    if args.action == "provision-plan":
        print("# First provisioning plan only. Inspect existing resources before executing each command.")
        print("# Never pipe this output to a shell; contains no secret values. Budget alerts are not a spending cap.")
        for command in provision_commands(c):
            print("rtk proxy " + shlex.join(command))
    else:
        require(args.images is not None, "--images is required")
        service, job = render(c, json.loads(args.images.read_text()))
        args.out.mkdir(parents=True, exist_ok=True)
        for name, document in [("service.json", service), ("import-job.json", job)]:
            (args.out / name).write_text(json.dumps(document, indent=2) + "\n")
        print("Rendered service and import job; no cloud action performed")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        sys.exit(f"staging configuration rejected: {error}")
