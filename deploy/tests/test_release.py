"""Offline contract/driver tests only; no fixture is cloud acceptance evidence."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release
import release_contracts as contracts
import release_evidence as evidence
import release_ops as ops
import staging
from test_staging import fixture as staging_fixture


def fixture():
    c, lock = staging_fixture()
    c["previous_revision"] = c["service"]+"-good"
    r = json.loads((Path(release.__file__).parent/"release.example.json").read_text())
    r.update(source_commit=lock["source_commit"], candidate_revision=c["service"]+"-"+c["revision_suffix"], approved_by="OFFLINE UNIT FIXTURE")
    r["known_good"] = {"revision": c["previous_revision"], "source_commit": "d"*40,
        "images": {role: value.replace("c"*64, "d"*64) for role, value in lock["images"].items()},
        "secrets": copy.deepcopy(c["secrets"]), "model_revision": "e"*40,
        "gemini_model": c["gemini_model"], "gemini_voice": c["gemini_voice"]}
    for ref in r["known_good"]["secrets"].values(): ref["version"] = "2"
    service, _ = staging.render(c, lock)
    service["metadata"]["resourceVersion"] = "one"
    service["status"] = {"conditions": [{"type": "Ready", "status": "True"}], "url": c["public_origin"],
        "latestCreatedRevisionName": r["candidate_revision"], "latestReadyRevisionName": r["candidate_revision"],
        "traffic": copy.deepcopy(service["spec"]["traffic"])}
    def revision(name, image_lock, refs):
        conf = dict(c, secrets=refs)
        rendered, _ = staging.render(conf, dict(lock, images=image_lock))
        return {"apiVersion": "serving.knative.dev/v1", "kind": "Revision",
            "metadata": dict(rendered["spec"]["template"]["metadata"], name=name, namespace=c["project_number"], labels={"serving.knative.dev/service": c["service"]}),
            "spec": rendered["spec"]["template"]["spec"], "status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    captures = {"captured_at": datetime.now(timezone.utc).isoformat(), "service": service,
        "candidate": revision(r["candidate_revision"], lock["images"], c["secrets"]),
        "known_good": revision(r["known_good"]["revision"], r["known_good"]["images"], r["known_good"]["secrets"]),
        "iam": {"etag": "policy-one", "bindings": [{"role": "roles/run.invoker", "members": ["user:offline@example.test"]}]}}
    return c, lock, r, captures


def reviews(c, r, path):
    subject = {"project_id": c["project_id"], "region": c["region"], "service": c["service"], "candidate_revision": r["candidate_revision"],
        "source_commit": r["source_commit"], "known_good_revision": r["known_good"]["revision"], "origin": c["public_origin"]}
    for name in contracts.CHECKS:
        facts = {"verified": True}
        if name == "baseline_qualification": facts = {"bundle": r["known_good"], "native_voice_and_backoffice_verified": True}
        if name == "schema_compatibility": facts = {"additive_only": True, "rollback_database_writes": False, "current_schema_version": "001", "baseline_schema_version": "001"}
        if name == "same_origin_access": facts = {"verified_browser_origin": c["public_origin"], "candidate_revision": r["candidate_revision"], "actual_native_session_verified": True}
        if name == "five_user_load": facts = {"simultaneous_live_sessions": 5, "typed_and_admin_requests_observed": True, "bounds_and_recovery_verified": True}
        if name == "optional_languages": facts = {"offered": [], "all_offered_smoke_passed": True}
        value = {"schema_version": "release-check-v1", "environment": "deployed", "subject": subject, "verdict": "pass", "reviewer": "OFFLINE FIXTURE", "check": name,
            "observed_at": datetime.now(timezone.utc).isoformat(), "facts": facts}
        file = path/(name+".json")
        file.write_text(json.dumps(value))
        r["checks"][name] = {"status": "pass", "reviewer": "OFFLINE FIXTURE", "artifact": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}


class Identities(unittest.TestCase):
    def test_candidate_model_change_keeps_baseline_settings_for_recovery(self):
        c, lock, r, captures = fixture()
        c.update(gemini_model="gemini-configured-live", gemini_voice="Aoede")
        row = next(x for x in captures["candidate"]["spec"]["containers"] if x["name"] == "adk")
        for entry in row["env"]:
            if entry["name"] == "GEMINI_MODEL": entry["value"] = c["gemini_model"]
            if entry["name"] == "GEMINI_VOICE": entry["value"] = c["gemini_voice"]
        ops.inspect(c, lock, r, captures, "promote")
        captures["service"]["status"]["traffic"] = [{"revisionName":r["candidate_revision"], "percent":100}]
        ops.inspect(c, lock, r, captures, "rollback")
        baseline = next(x for x in captures["known_good"]["spec"]["containers"] if x["name"] == "adk")
        next(x for x in baseline["env"] if x["name"] == "GEMINI_MODEL")["value"] = c["gemini_model"]
        with self.assertRaises(ValueError):
            ops.inspect(c, lock, r, captures, "rollback")

    def test_unreviewed_gemini_model_or_voice_drift_is_rejected(self):
        for name in ("GEMINI_MODEL", "GEMINI_VOICE"):
            with self.subTest(name=name):
                c, lock, r, captures = fixture()
                row = next(x for x in captures["candidate"]["spec"]["containers"] if x["name"] == "adk")
                next(x for x in row["env"] if x["name"] == name)["value"] = "unreviewed-change"
                with self.assertRaises(ValueError):
                    ops.inspect(c, lock, r, captures, "promote")

    def test_exact_revision_and_secret_bundle(self):
        c, lock, r, captures = fixture()
        view = ops.inspect(c, lock, r, captures, "promote")
        self.assertEqual(view["baseline"]["secret_refs"]["gemini-api-key"]["version"], "2")
        self.assertEqual(view["candidate"]["images"], lock["images"])
        captures['candidate']['spec']['containers'][0]['resources']['limits']['cpu'] = '1000m'
        ops.inspect(c, lock, r, captures, 'promote')
        captures['service']['status']['traffic'] = [{'revisionName':r['candidate_revision'], 'percent':100}]
        final_capture = release.sanitized(c, lock, r, captures, 'verify')
        self.assertIsNotNone(final_capture['candidate'])
        ops.inspect(c, lock, r, final_capture, 'verify')

    def test_namespace_foreign_revision_and_floating_traffic(self):
        for mode in ("namespace", "foreign", "latest", "percent"):
            c, lock, r, captures = fixture()
            if mode == "namespace": captures["service"]["metadata"]["namespace"] = "999999"
            if mode == "foreign": captures["service"]["status"]["traffic"][0]["revisionName"] = "another-service-test"
            if mode == "latest": captures["service"]["status"]["traffic"][0]["latestRevision"] = True
            if mode == "percent": captures["service"]["status"]["traffic"][1]["percent"] = True
            with self.assertRaises(ValueError): ops.inspect(c, lock, r, captures, "promote")

    def test_mixed_images_literal_secret_and_bad_pin(self):
        for mode in ("image", "literal", "pin", "missing_role", "entrypoint", "mount"):
            c, lock, r, captures = fixture()
            row = captures["candidate"]["spec"]["containers"][1]
            if mode == "image": row["image"] = r["known_good"]["images"]["adk"]
            if mode == "literal": row["env"][0] = {"name": "GOOGLE_API_KEY", "value": "synthetic-forbidden-value"}
            if mode == "pin": row["env"][0]["valueFrom"]["secretKeyRef"]["key"] = "latest"
            if mode == "missing_role": captures["candidate"]["spec"]["containers"].pop()
            if mode == "entrypoint": row["command"] = ["fixture-server"]
            if mode == "mount": row["volumeMounts"] = [{"name":"unreviewed-secret","mountPath":"/app"}]
            with self.assertRaises(ValueError): ops.inspect(c, lock, r, captures, "promote")

    def test_sidecar_ingress_http2_and_runtime_limits(self):
        for mode in ("private_port", "http2", "concurrency", "sql", "origin", "billing", "service_scaling"):
            c, lock, r, captures = fixture()
            spec = captures["candidate"]["spec"]
            if mode == "private_port": spec["containers"][2]["ports"] = [{"containerPort": 8003}]
            if mode == "http2": spec["containers"][0]["ports"][0]["name"] = "h2c"
            if mode == "concurrency": spec["containerConcurrency"] = 100
            if mode == "sql": captures["candidate"]["metadata"]["annotations"]["run.googleapis.com/cloudsql-instances"] = "foreign-project:region:db"
            if mode == "origin": next(e for e in spec["containers"][0]["env"] if e["name"] == "PUBLIC_ORIGIN")["value"] = "https://candidate-tag.example.test"
            if mode == "billing": captures["candidate"]["metadata"]["annotations"]["run.googleapis.com/cpu-throttling"] = "false"
            if mode == "service_scaling": captures["service"]["metadata"]["annotations"]["run.googleapis.com/maxScale"] = "20"
            with self.assertRaises(ValueError): ops.inspect(c, lock, r, captures, "promote")

    def test_failed_candidate_does_not_block_qualified_rollback(self):
        c, lock, r, captures = fixture()
        captures["candidate"] = None
        captures["service"]["status"]["conditions"][0]["status"] = "False"
        captures["service"]["status"]["traffic"] = [{"revisionName": r["candidate_revision"], "percent": 100}]
        self.assertIsNone(ops.inspect(c, lock, r, captures, "rollback")["candidate"])

    def test_private_public_iam_and_disabled_invoker(self):
        for mode in ("public", "privileged", "disabled"):
            c, lock, r, captures = fixture()
            if mode == "public": captures["iam"]["bindings"][0]["members"] = ["allUsers"]
            if mode == "privileged": c["reviewer_access"] = "public"; captures["iam"]["bindings"] += [{"role": "roles/run.admin", "members": ["allUsers"]}]
            if mode == "disabled": captures["service"]["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = "true"
            with self.assertRaises(ValueError): ops.inspect(c, lock, r, captures, "promote")

    def test_snapshot_redacts_principals_and_arbitrary_metadata(self):
        c, lock, r, captures = fixture()
        captures["candidate"]["metadata"]["annotations"]["arbitrary-private-note"] = "synthetic-private-value"
        captures["service"]["status"]["private-message"] = "synthetic-private-value"
        sanitized = release.sanitized(c, lock, r, captures, "promote")
        raw = json.dumps(sanitized)
        self.assertNotIn("offline@example.test", raw)
        self.assertNotIn("synthetic-private-value", raw)
        self.assertEqual(ops.inspect(c, lock, r, sanitized, "promote"), ops.inspect(c, lock, r, captures, "promote"))
        class ReadOnlyFault:
            def call(self, args):
                result = copy.deepcopy(captures['candidate'])
                result['metadata']['name'] = c['service']+'-fault'
                return result
        fault = release.fault_capture(c, r, c['service']+'-fault', ReadOnlyFault())
        self.assertNotIn('spec', fault)
        self.assertNotIn('synthetic-private-value', json.dumps(fault))
        with self.assertRaises(ValueError): release.fault_capture(c, r, r['candidate_revision'], ReadOnlyFault())

    def test_credential_urls_and_revision_injection_rejected(self):
        for url in ("http://example.test", "https://user:password@example.test", "https://example.test/?key=x", "https://127.0.0.2", "https://[::1]"):
            with self.assertRaises(ValueError): contracts.origin(url)
        c, _, r, _ = fixture()
        r["candidate_revision"] = c["service"]+"-next;echo injected"
        with self.assertRaises(ValueError): contracts.validate_release(c, r)


class Evidence(unittest.TestCase):
    def test_empty_release_template_never_qualifies(self):
        c, _, _, _ = fixture()
        blank = json.loads((Path(release.__file__).parent/"release.example.json").read_text())
        with self.assertRaises(ValueError): contracts.validate_release(c, blank)

    def test_review_hash_identity_and_same_origin(self):
        c, _, r, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            reviews(c, r, path)
            self.assertEqual(len(evidence.checks(c, r, path, "promote")), 11)
            file = path/"same_origin_access.json"
            value = json.loads(file.read_text())
            value["facts"]["verified_browser_origin"] = "https://tagged.example.test"
            file.write_text(json.dumps(value))
            with self.assertRaises(ValueError): evidence.checks(c, r, path, "promote")
            r["checks"]["same_origin_access"]["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
            with self.assertRaises(ValueError): evidence.checks(c, r, path, "promote")

    def test_rollback_needs_baseline_and_schema_not_failed_candidate_qa(self):
        c, _, r, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            reviews(c, r, path)
            (path/"candidate_native_smoke.json").unlink()
            self.assertEqual(set(evidence.checks(c, r, path, "rollback")), contracts.RECOVERY_CHECKS)
            (path/"schema_compatibility.json").unlink()
            with self.assertRaises(ValueError): evidence.checks(c, r, path, "rollback")

    def test_never_reverts_database_writes(self):
        c, _, r, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder); reviews(c, r, path)
            file = path/"schema_compatibility.json"; value = json.loads(file.read_text())
            value["facts"]["rollback_database_writes"] = True
            file.write_text(json.dumps(value))
            r["checks"]["schema_compatibility"]["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
            with self.assertRaises(ValueError): evidence.checks(c, r, path, "rollback")

    def test_wrong_environment_artifact_symlink_and_traversal(self):
        c, _, r, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder); reviews(c, r, path)
            check = r["checks"]["privacy"]
            check["artifact"] = "../privacy.json"
            with self.assertRaises(ValueError): evidence.checks(c, r, path, "promote")
            check["artifact"] = "privacy.json"
            file = path/check["artifact"]; saved = file.read_bytes(); file.unlink()
            (path/"other.json").write_bytes(saved); file.symlink_to(path/"other.json")
            with self.assertRaises(ValueError): evidence.checks(c, r, path, "promote")


class Planning(unittest.TestCase):
    def test_source_tag_identity_versions_and_missing_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args): return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()
            git('init', '-b', 'main'); git('config', 'user.name', 'Offline fixture'); git('config', 'user.email', 'offline@example.test')
            for name in ('package.json', 'web/package.json'):
                file = root/name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('{"version":"0.1.0"}')
            git('add', '.'); git('commit', '-m', 'incomplete offline fixture')
            sha = git('rev-parse', 'HEAD'); git('update-ref', 'refs/remotes/origin/main', sha); git('tag', '-a', 'v0.1.0', '-m', 'fixture')
            result = contracts.source_audit(root, 'v0.1.0', sha)
            self.assertEqual(result['status'], 'blocked')
            self.assertIn('agent/tools/intent.py', result['missing_build_inputs'])
            with self.assertRaises(ValueError): contracts.source_audit(root, 'v0.1.0', 'f'*40)
            git('tag', 'v0.1.1')
            with self.assertRaises(ValueError): contracts.source_audit(root, 'v0.1.1')
    def test_named_commands_have_no_iam_sql_or_latest(self):
        c, _, r, _ = fixture()
        for revision in (r["candidate_revision"], r["known_good"]["revision"]):
            cmd = ops.traffic_command(c, revision)
            self.assertIn("--to-revisions="+revision+"=100", cmd)
            self.assertIn("--project=unit-project", cmd)
            self.assertIn("--region=asia-southeast1", cmd)
            self.assertFalse(any("LATEST" in x or "--async" == x or "iam-policy-binding" in x or "sql" == x for x in cmd))

    def test_promotion_denies_missing_qa_despite_healthy_cloud(self):
        c, lock, r, captures = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder); reviews(c, r, path)
            with patch.object(release, "source_audit", return_value={"status": "pass"}):
                with self.assertRaises(ValueError): release.make_plan(path, c, lock, r, captures, path, "promote")

    def test_snapshot_stale_and_traffic_drift_block_plan(self):
        c, lock, r, captures = fixture()
        captures["captured_at"] = (datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat()
        with self.assertRaises(ValueError): release.make_plan(Path.cwd(), c, lock, r, captures, Path.cwd(), "rollback")
        captures["captured_at"] = datetime.now(timezone.utc).isoformat()
        with self.assertRaises(ValueError): release.make_plan(Path.cwd(), c, lock, r, captures, Path.cwd(), "rollback")


class FakeCloud:
    def __init__(self, captures, target):
        self.data = copy.deepcopy(captures); self.target = target; self.commands = []; self.recorded = []
        self.fail = False; self.wrong_percent = False
    def capture(self, *args): return copy.deepcopy(self.data)
    def call(self, cmd, timeout):
        assert self.recorded, "intent must be durable before mutation"
        self.commands.append(cmd)
        if self.fail: raise subprocess.TimeoutExpired("gcloud", timeout)
        self.data["service"]["metadata"]["resourceVersion"] = "two"
        self.data["service"]["status"]["traffic"] = [{"revisionName": self.target, "percent": 80 if self.wrong_percent else 100}]
        return {}


class Execution(unittest.TestCase):
    def test_rollback_restores_baseline_model_and_voice_after_candidate_change(self):
        c, lock, r, captures = fixture()
        c.update(gemini_model="gemini-configured-live", gemini_voice="Aoede")
        captures["service"]["status"]["traffic"] = [{"revisionName":r["candidate_revision"], "percent":100}]
        plan = {"operation": "rollback", "context_sha256": contracts.digest({"config": c, "images": lock, "release": r}),
                "expected_state_sha256": contracts.digest(ops.inspect(c, lock, r, captures, "rollback"))}
        cloud = FakeCloud(captures, r["known_good"]["revision"])
        result = ops.execute(c, lock, r, plan, cloud, lambda value: cloud.recorded.append(copy.deepcopy(value)))
        self.assertEqual(result["state"], "TRAFFIC_VERIFIED_SMOKE_PENDING")
        self.assertEqual(result["target_revision"], r["known_good"]["revision"])

    def setup_plan(self):
        c, lock, r, captures = fixture()
        plan = {"operation": "promote", "context_sha256": contracts.digest({"config": c, "images": lock, "release": r}),
            "expected_state_sha256": contracts.digest(ops.inspect(c, lock, r, captures, "promote"))}
        cloud = FakeCloud(captures, r["candidate_revision"])
        return c, lock, r, plan, cloud

    def test_live_drift_causes_zero_mutations(self):
        c, lock, r, plan, cloud = self.setup_plan()
        cloud.data["iam"]["etag"] = "policy-two"
        with self.assertRaises(ValueError): ops.execute(c, lock, r, plan, cloud)
        self.assertEqual(cloud.commands, [])

    def test_changed_plan_context_causes_zero_mutations(self):
        c, lock, r, plan, cloud = self.setup_plan()
        r["approved_by"] = "changed approval"
        with self.assertRaises(ValueError): ops.execute(c, lock, r, plan, cloud)
        self.assertEqual(cloud.commands, [])

    def test_effective_traffic_is_smoke_pending_not_release_success(self):
        c, lock, r, plan, cloud = self.setup_plan()
        def record(value): cloud.recorded.append(copy.deepcopy(value))
        result = ops.execute(c, lock, r, plan, cloud, record)
        self.assertEqual(len(cloud.commands), 1)
        self.assertEqual(cloud.recorded[0]["state"], "CHANGE_ATTEMPTED_VERIFY_PENDING")
        self.assertEqual(result["state"], "TRAFFIC_VERIFIED_SMOKE_PENDING")
        self.assertEqual(result["target_source_commit"], r["source_commit"])

    def test_timeout_or_wrong_effective_traffic_never_retries_or_passes(self):
        for mode in ("fail", "wrong_percent"):
            c, lock, r, plan, cloud = self.setup_plan()
            setattr(cloud, mode, True)
            result = ops.execute(c, lock, r, plan, cloud, lambda value: cloud.recorded.append(copy.deepcopy(value)))
            self.assertEqual(len(cloud.commands), 1)
            self.assertEqual(result["state"], "CHANGE_ATTEMPTED_RESULT_UNVERIFIED")

    def test_existing_operation_file_and_missing_execute_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder); out = path/"receipt.json"; out.write_text('old-record')
            cmd = [sys.executable, str(Path(release.__file__)), "execute", "--config", "missing", "--images", "missing", "--release", "missing", "--evidence", "missing", "--captures", "missing", "--plan", "missing", "--out", str(out)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(out.read_text(), 'old-record')
            self.assertNotIn('Traceback', result.stderr)


class Finalization(unittest.TestCase):
    def case(self, path, recovery_seconds=60):
        c, lock, r, captures = fixture(); reviews(c, r, path)
        # Explicit synthetic unit observations; never exported as cloud acceptance.
        now = datetime.now(timezone.utc)
        start = now-timedelta(seconds=recovery_seconds+120)
        context = contracts.digest({"config": c, "images": lock, "release": r})
        operations, proofs = [], {}
        for i, (op, key, offset) in enumerate((('promote','post_promotion',0), ('rollback','rollback',20), ('promote','final_promotion',recovery_seconds+50))):
            good = r['known_good'] if i==1 else {"revision":r['candidate_revision'], "source_commit":r['source_commit'], "images":lock['images'], "model_revision":'a'*40}
            when = start+timedelta(seconds=offset)
            operation = {"schema_version":"release-operation-v1", "state":"TRAFFIC_VERIFIED_SMOKE_PENDING", "operation":op,
                "project_id":c['project_id'], "region":c['region'], "service":c['service'], "source_commit":r['source_commit'],
                "target_revision":good['revision'], "target_source_commit":good['source_commit'], "images":good['images'],
                "started_at":when.isoformat(), "verified_at":(when+timedelta(seconds=1)).isoformat(),
                "traffic_operation_ms":1000, "plan_sha256":'a'*64, "context_sha256":context}
            operations.append(operation)
            observed_at = when+timedelta(seconds=recovery_seconds if i==1 else 2)
            subject = {"project_id":c['project_id'], "region":c['region'], "service":c['service'], "revision":good['revision'],
                "source_commit":good['source_commit'], "origin":c['public_origin'], "operation_sha256":contracts.digest(operation)}
            value = {"schema_version":"release-check-v1", "environment":"deployed", "subject":subject, "verdict":"pass", "reviewer":"OFFLINE FIXTURE", "check":"native_release_smoke",
                "observed_at":observed_at.isoformat(), "facts":dict.fromkeys(evidence.SMOKE_FACTS, True)}
            value['facts'].update(images=good['images'], model_revision=good['model_revision'])
            file = path/(key+'.json'); file.write_text(json.dumps(value))
            proofs[key] = {"status":"pass", "reviewer":"OFFLINE FIXTURE", "artifact":file.name, "sha256":hashlib.sha256(file.read_bytes()).hexdigest()}
        captures['service']['status']['traffic'] = [{"revisionName":r['candidate_revision'], "percent":100}]
        name = c['service']+'-fault'
        captured = {'apiVersion':'serving.knative.dev/v1','kind':'Revision','captured_at':(start+timedelta(seconds=8)).isoformat(),
            'metadata':{'name':name,'namespace':c['project_number'],'labels':{'serving.knative.dev/service':c['service']}},'status':{'conditions':[{'type':'Ready','status':'False'}]}}
        file = path/'fault-capture.json'; file.write_text(json.dumps(captured))
        subject = {'project_id':c['project_id'],'region':c['region'],'service':c['service'],'candidate_revision':r['candidate_revision'],
            'source_commit':r['source_commit'],'known_good_revision':r['known_good']['revision'],'origin':c['public_origin'],'operation_sha256':contracts.digest(operations[1])}
        fault = {'schema_version':'release-check-v1','environment':'deployed','subject':subject,'verdict':'pass','reviewer':'OFFLINE FIXTURE',
            'check':'rollback_fault_injection','observed_at':(start+timedelta(seconds=10)).isoformat(),
            'facts':{'failure_observed':True,'test_traffic_isolated':True,'ordinary_database_preserved':True,'failing_revision':name,
                     'revision_capture':file.name,'revision_capture_sha256':hashlib.sha256(file.read_bytes()).hexdigest()}}
        file=path/'fault-proof.json';file.write_text(json.dumps(fault))
        proofs['fault_injection']={'status':'pass','reviewer':'OFFLINE FIXTURE','artifact':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
        return c, lock, r, captures, operations, proofs

    def test_complete_rehearsal_qualifies_owner_record_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); c, lock, r, captures, operations, proofs=self.case(path)
            with patch.object(release, 'qa', return_value={'model_revision':'a'*40}):
                result=release.finalize(c,lock,r,path,operations,proofs,captures)
            self.assertEqual(result['state'],'ELIGIBLE_FOR_OWNER_DEPLOYMENT_RECORD')
            self.assertEqual(result['rollback_recovery_seconds'],60)

    def test_recovery_beyond_fifteen_minutes_fails_including_native_smoke(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); c,lock,r,captures,operations,proofs=self.case(path,901)
            with patch.object(release,'qa',return_value={'model_revision':'a'*40}):
                with self.assertRaisesRegex(ValueError,'15 minutes'): release.finalize(c,lock,r,path,operations,proofs,captures)

    def test_missing_native_smoke_or_final_promotion_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); c,lock,r,captures,operations,proofs=self.case(path)
            with self.assertRaises(ValueError): release.finalize(c,lock,r,path,operations[:2],proofs,captures)
            (path/'rollback.json').unlink()
            with patch.object(release,'qa',return_value={'model_revision':'a'*40}):
                with self.assertRaises(ValueError): release.finalize(c,lock,r,path,operations,proofs,captures)

    def test_old_smoke_cannot_bind_to_changed_operation_or_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); c,lock,r,captures,operations,proofs=self.case(path)
            operations[0]['plan_sha256']='b'*64
            with patch.object(release,'qa',return_value={'model_revision':'a'*40}):
                with self.assertRaises(ValueError): release.finalize(c,lock,r,path,operations,proofs,captures)

    def test_final_traffic_or_bundle_drift_blocks_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); c,lock,r,captures,operations,proofs=self.case(path)
            captures['candidate']['spec']['containers'][0]['image']=r['known_good']['images']['go']
            with patch.object(release,'qa',return_value={'model_revision':'a'*40}):
                with self.assertRaises(ValueError): release.finalize(c,lock,r,path,operations,proofs,captures)

    def test_final_capture_must_follow_final_native_smoke(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            c, lock, r, captures, operations, proofs = self.case(path)
            completed = evidence.utc(evidence.read_json(path / 'final_promotion.json')['observed_at'])
            with patch.object(release, 'qa', return_value={'model_revision': 'a'*40}):
                # Each is recent and shows the candidate, but predates completion.
                for stamp in (operations[0]['verified_at'], operations[2]['verified_at'],
                              (completed - timedelta(microseconds=1)).isoformat()):
                    with self.subTest(captured_at=stamp):
                        captures['captured_at'] = stamp
                        with self.assertRaisesRegex(ValueError, 'final cloud snapshot predates final smoke'):
                            release.finalize(c, lock, r, path, operations, proofs, captures)
                captures['captured_at'] = completed.isoformat()
                result = release.finalize(c, lock, r, path, operations, proofs, captures)
                self.assertEqual(result['state'], 'ELIGIBLE_FOR_OWNER_DEPLOYMENT_RECORD')

    def test_missing_isolated_fault_rehearsal_blocks_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); c,lock,r,captures,operations,proofs=self.case(path)
            (path/'fault-capture.json').unlink()
            with patch.object(release,'qa',return_value={'model_revision':'a'*40}):
                with self.assertRaises(ValueError): release.finalize(c,lock,r,path,operations,proofs,captures)


if __name__ == "__main__": unittest.main()
