"""Strict, secret-free Cloud Run release identities and captured state."""
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from staging import SECRET_ENV, account, require, matches, secret_env, gemini_env, validate_gemini, connection

ROLES = {"go", "adk", "laya"}
CHECKS = {"build_provenance", "baseline_qualification", "schema_compatibility", "same_origin_access",
          "secret_versions_available", "candidate_native_smoke", "persistence", "privacy",
          "five_user_load", "monitoring_owner", "optional_languages"}
RECOVERY_CHECKS = {"baseline_qualification", "schema_compatibility", "secret_versions_available", "monitoring_owner"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def origin(value):
    require(isinstance(value, str), "HTTPS origin required")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path == "", "credential-free exact HTTPS origin required")
    local = parsed.hostname == "localhost"
    try:
        local |= ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    require(not local, "local fixtures are not release origins")
    return value


def target(c):
    require(matches(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", c.get("project_id")), "project identity missing")
    require(matches(r"[0-9]{6,}", c.get("project_number")), "project number missing")
    require(matches(r"[a-z]+-[a-z]+[0-9]", c.get("region")), "region missing")
    for key in ("service", "repository", "sql_instance"):
        require(matches(r"[a-z][a-z0-9-]{2,39}", c.get(key)), "service/repository/SQL identity missing")
    require(isinstance(c.get("approved_by"), str) and c["approved_by"].strip(), "cloud authorization record missing")
    require(c.get("reviewer_access") in ("private", "public"), "access selection missing")
    origin(c.get("public_origin"))


def revision_name(c, name):
    require(matches(re.escape(c["service"])+r"-[a-z0-9-]+", name), "revision belongs to a different service")
    return name


def images(c, values):
    require(isinstance(values, dict) and set(values) == ROLES, "matched three-image bundle required")
    prefix = f'{c["region"]}-docker.pkg.dev/{c["project_id"]}/{c["repository"]}/'
    for role, image in values.items():
        require(matches(re.escape(prefix+role)+r"@sha256:[0-9a-f]{64}", image), "runtime image must be an immutable configured registry digest")


def secrets(values):
    expected = set().union(*(set(v.values()) for v in SECRET_ENV.values()))
    require(isinstance(values, dict) and set(values) == expected, "exact secret role inventory required")
    for ref in values.values():
        require(isinstance(ref, dict) and set(ref) == {"name", "version"}, "secret references only, never values")
        require(matches(r"[a-z][a-z0-9-]{2,100}", ref["name"]) and matches(r"[1-9][0-9]*", ref["version"]), "numeric pinned secret versions required")
    require(len({v["name"] for v in values.values()}) == len(values), "secret roles cannot share names")


def validate_release(c, r):
    validate_gemini(c)
    expected = {"schema_version", "git_tag", "source_commit", "candidate_revision", "approved_by",
                "known_good", "qa_observations", "qa_http_run", "qa_artifacts", "checks"}
    require(isinstance(r, dict) and set(r) == expected and r["schema_version"] == "release-v1", "release schema differs")
    require(matches(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", r["git_tag"]) and matches(r"[0-9a-f]{40}", r["source_commit"]), "real SemVer tag/full source commit required")
    require(isinstance(r["approved_by"], str) and r["approved_by"].strip(), "release operator approval record missing")
    revision_name(c, r["candidate_revision"])
    good = r["known_good"]
    require(isinstance(good, dict) and set(good) == {"revision", "source_commit", "images", "secrets", "model_revision", "gemini_model", "gemini_voice"}, "known-good bundle differs")
    validate_gemini(good)
    revision_name(c, good["revision"])
    require(good["revision"] != r["candidate_revision"] and c.get("previous_revision") == good["revision"], "distinct, configured rollback baseline required")
    require(matches(r"[0-9a-f]{40}", good["source_commit"]) and matches(r"[0-9a-f]{40}", good["model_revision"]), "baseline source/checkpoint identity missing")
    images(c, good["images"])
    secrets(good["secrets"])
    require(isinstance(r["checks"], dict) and set(r["checks"]) == CHECKS, "release check inventory differs")
    for key in ("qa_observations", "qa_http_run", "qa_artifacts"):
        require(matches(r"[A-Za-z0-9_-]+(?:\.json)?", r[key]), "evidence paths must be single local names")


def identity(c, value, name, kind):
    require(isinstance(value, dict) and value.get("kind") == kind, "Cloud Run v1 object kind differs")
    require(value.get("apiVersion") == "serving.knative.dev/v1", "Cloud Run v1 export required")
    metadata = value["metadata"]
    require(isinstance(metadata, dict), "resource metadata object required")
    require(metadata.get("name") == name and str(metadata.get("namespace")) == c["project_number"], "Cloud Run resource identity differs")
    return metadata


def ready(value):
    status = value.get("status", {})
    require(isinstance(status, dict) and isinstance(status.get("conditions", []), list) and all(isinstance(c, dict) for c in status.get("conditions", [])), "condition objects required")
    return any(c.get("type") == "Ready" and c.get("status") == "True" for c in status.get("conditions", []))


def service_view(c, value):
    metadata = identity(c, value, c["service"], "Service")
    require(isinstance(metadata.get("resourceVersion"), str) and metadata["resourceVersion"], "service resource version missing")
    require(metadata.get("annotations", {}).get("run.googleapis.com/invoker-iam-disabled", "false") == "false", "invoker IAM check disabled")
    require(metadata.get("labels", {}).get("cloud.googleapis.com/location") == c["region"], "service region differs")
    service_annotations = metadata.get("annotations", {})
    require(service_annotations.get("run.googleapis.com/minScale", "0") == "0" and service_annotations.get("run.googleapis.com/maxScale", "2") == "2", "service-level scaling differs from release limits")
    rows, percentages = [], {}
    require(isinstance(value.get("status"), dict) and isinstance(value["status"].get("traffic"), list) and all(isinstance(row, dict) for row in value["status"]["traffic"]), "traffic objects required")
    for row in value["status"]["traffic"]:
        name = revision_name(c, row.get("revisionName"))
        require(not row.get("latestRevision"), "floating latest traffic is forbidden")
        percent = row.get("percent", 0)
        require(type(percent) is int and 0 <= percent <= 100, "invalid traffic percentage")
        percentages[name] = percentages.get(name, 0)+percent
        tag = row.get("tag")
        require(tag is None or matches(r"[a-z][a-z0-9-]{0,62}", tag), "invalid traffic tag")
        rows.append({"revision": name, "percent": percent, "tag": tag})
    require(sum(percentages.values()) == 100, "traffic must total 100 percent")
    return {"name": c["service"], "project_number": c["project_number"], "region": c["region"],
            "resource_version": metadata["resourceVersion"], "ready": ready(value),
            "latest_created": revision_name(c, value["status"]["latestCreatedRevisionName"]),
            "latest_ready": revision_name(c, value["status"]["latestReadyRevisionName"]),
            "service_origin": origin(value["status"]["url"]), "traffic": sorted(rows, key=lambda r: (r["revision"], r["tag"] or "", r["percent"])),
            "percentages": percentages}


def revision_view(c, value, name, bundle, secret_refs, *, must_be_ready=True):
    metadata = identity(c, value, revision_name(c, name), "Revision")
    require(metadata.get("labels", {}).get("serving.knative.dev/service") == c["service"], "revision service label differs")
    require(not must_be_ready or ready(value), "target revision is not Ready")
    images(c, bundle)
    secrets(secret_refs)
    spec = value["spec"]
    require(isinstance(spec, dict), "revision spec object required")
    require(spec["serviceAccountName"] == account(c, "runtime") and type(spec["containerConcurrency"]) is int and spec["containerConcurrency"] == 10 and type(spec["timeoutSeconds"]) is int and spec["timeoutSeconds"] == 660, "runtime identity/limits differ")
    require(not spec.get("volumes") and not spec.get("nodeSelector"), "unreviewed volume/GPU runtime override")
    annotations = metadata.get("annotations", {})
    for key, expected in {"run.googleapis.com/cloudsql-instances": connection(c), "autoscaling.knative.dev/maxScale": "2", "autoscaling.knative.dev/minScale": "0", "run.googleapis.com/execution-environment": "gen2", "run.googleapis.com/cpu-throttling": "true"}.items():
        require(annotations.get(key) == expected, "runtime SQL/scaling contract differs")
    require(json.loads(annotations.get("run.googleapis.com/container-dependencies", "{}")) == {"go": ["adk"], "adk": ["laya"]}, "private startup dependencies differ")
    rows = spec["containers"]
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), "container objects required")
    require(len(rows) == 3 and {row["name"] for row in rows} == ROLES, "exact three-container revision required")
    adjusted = dict(c, secrets=secret_refs)
    for row in rows:
        role = row["name"]
        require(row["image"] == bundle[role] and not row.get("command") and not row.get("args") and not row.get("workingDir") and not row.get("volumeMounts"), "image/entrypoint/mount differs from reviewed bundle")
        expected = {entry["name"]: entry for entry in secret_env(adjusted, role)}
        if role == "go":
            expected.update({key: {"name": key, "value": val} for key, val in {"READINESS_MODE": "full", "STATIC_DIR": "/app/web/build", "PUBLIC_ORIGIN": c["public_origin"], "VOICE_ENABLED": "true"}.items()})
        elif role == "adk":
            expected.update({entry["name"]: entry for entry in gemini_env(c)})
        env = row.get("env", [])
        require(isinstance(env, list) and all(isinstance(entry, dict) for entry in env), "environment objects required")
        require(len(env) == len(expected) and {entry["name"] for entry in env} == set(expected), "unexpected/missing runtime environment")
        require(all(entry == expected[entry["name"]] for entry in env), "runtime environment/secret pins differ; literal secrets forbidden")
        limits = row["resources"]["limits"]
        cpu = {"2", "2000m"} if role == "laya" else {"1", "1000m"}
        memory = {"4Gi", "4096Mi", "4294967296"} if role == "laya" else {"512Mi", "536870912"}
        require(isinstance(limits, dict) and set(limits) == {"cpu", "memory"} and limits["cpu"] in cpu and limits["memory"] in memory, "runtime resources differ")
        require(row.get("ports", []) == ([{"name": "http1", "containerPort": 8080}] if role == "go" else []), "private sidecar is exposed or HTTP2 is enabled")
        probe = row.get("startupProbe", {}).get("httpGet", {})
        require(probe == {"path": "/readyz" if role == "go" else "/healthz", "port": {"go": 8080, "adk": 8001, "laya": 8003}[role]}, "startup probe contract differs")
        if role == "go":
            require(row.get("livenessProbe", {}).get("httpGet") == {"path": "/healthz", "port": 8080}, "Go liveness probe differs")
    # Only safe identities/pins are returned, never arbitrary metadata/env values.
    return {"revision": name, "ready": ready(value), "images": bundle, "secret_refs": secret_refs}


def iam_view(c, value):
    require(isinstance(value, dict) and isinstance(value.get("bindings", []), list), "IAM policy object required")
    public = any("allUsers" in b.get("members", []) or "allAuthenticatedUsers" in b.get("members", []) for b in value.get("bindings", []))
    require(not any(b.get("role") != "roles/run.invoker" and set(b.get("members", [])) & {"allUsers", "allAuthenticatedUsers"} for b in value.get("bindings", [])), "public privileged IAM binding observed")
    require(c["reviewer_access"] == "public" or not public, "private service has public IAM bindings")
    require(c["reviewer_access"] != "public" or any(b.get("role") == "roles/run.invoker" and "allUsers" in b.get("members", []) and not b.get("condition") for b in value.get("bindings", [])), "approved public invoker policy not observed")
    require(isinstance(value.get("etag"), str) and re.fullmatch(r"[A-Za-z0-9+=/_-]{1,200}", value["etag"]), "IAM etag missing")
    return {"access": c["reviewer_access"], "public_binding_present": public, "etag": value["etag"]}


def git(root, *args):
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=15)
    require(run.returncode == 0, "source Git identity unavailable")
    return run.stdout


def source_audit(root, tag, commit=None):
    from build import REQUIRED
    require(matches(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag), "SemVer tag required")
    actual = git(root, "rev-parse", "refs/tags/"+tag+"^{commit}").decode().strip()
    require(git(root, "cat-file", "-t", "refs/tags/"+tag).decode().strip() == "tag", "annotated tag required")
    require(commit is None or actual == commit, "tag/source commit mismatch")
    git(root, "merge-base", "--is-ancestor", actual, "origin/main")
    paths = set(git(root, "ls-tree", "-r", "--name-only", actual).decode().splitlines())
    missing = sorted(set(REQUIRED)-paths)
    if not any(p.startswith("internal/routing/") and p.endswith(".go") for p in paths):
        missing.append("internal/routing/*.go")
    versions = [json.loads(git(root, "show", actual+":"+name))["version"] for name in ("package.json", "web/package.json")]
    require(all("v"+v == tag for v in versions), "package version/tag mismatch")
    return {"tag": tag, "source_commit": actual, "status": "blocked" if missing else "pass", "missing_build_inputs": missing}
