import copy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build
import staging
from verify_model import verify


def fixture():
    c = json.loads((Path(staging.__file__).parent / "staging.example.json").read_text())
    c.update(project_id="unit-project", project_number="123456789012", sql_tier="db-custom-1-3840",
             sql_storage_gb=10, billing_account="ABCDEF-123456-ABCDEF", budget_amount="25USD",
             budget_notification_channel="projects/123456789012/notificationChannels/12",
             cleanup_date=str(date.today() + timedelta(days=1)), approved_by="offline test fixture only",
             reviewer_access="private", public_origin="https://example.test", revision_suffix="test-123")
    for secret in c["secrets"].values():
        secret["version"] = "1"
    lock = {"source_commit": "a" * 40,
            "bases": {key: "example.test/base@sha256:" + "b" * 64 for key in staging.BASE_KEYS},
            "images": {name: f'asia-southeast1-docker.pkg.dev/unit-project/prompt-shop/{name}@sha256:' + "c" * 64
                       for name in ("go", "adk", "laya")}, "integration_evidence": "offline fixture only"}
    return c, lock


class Manifests(unittest.TestCase):
    def test_gemini_settings_are_configurable_and_adk_only(self):
        c, lock = fixture()
        c.update(gemini_model="models/gemini-configured-live", gemini_voice="Aoede")
        service, job = staging.render(c, lock)
        for row in service["spec"]["template"]["spec"]["containers"]:
            selected = {entry["name"]: entry["value"] for entry in row["env"] if entry["name"] in {"GEMINI_MODEL", "GEMINI_VOICE"}}
            self.assertEqual(selected, {"GEMINI_MODEL": c["gemini_model"], "GEMINI_VOICE": "Aoede"} if row["name"] == "adk" else {})
        self.assertNotIn("GEMINI_MODEL", json.dumps(job))

    def test_gemini_settings_reject_malformed_values(self):
        for field, value in [("gemini_model", ""), ("gemini_model", "https://example.test/model"),
                             ("gemini_voice", None), ("gemini_voice", "Aoede\nInjected")]:
            with self.subTest(field=field, value=value):
                c, lock = fixture()
                c[field] = value
                with self.assertRaises(ValueError):
                    staging.render(c, lock)

    def test_secret_isolation_and_migration_identity(self):
        c, lock = fixture()
        service, job = staging.render(c, lock)
        spec = service["spec"]["template"]["spec"]
        containers = {x["name"]: x for x in spec["containers"]}
        for role, container in containers.items():
            secrets = {x["name"] for x in container["env"] if "valueFrom" in x}
            self.assertEqual(set(staging.SECRET_ENV[role]), secrets)
            self.assertTrue(all("value" not in x for x in container["env"] if x["name"] in secrets))
        self.assertNotIn("ports", containers["adk"])
        self.assertNotIn("ports", containers["laya"])
        self.assertEqual(containers["go"]["ports"], [{"name": "http1", "containerPort": 8080}])
        jspec = job["spec"]["template"]["spec"]["template"]["spec"]
        self.assertEqual(jspec["maxRetries"], 0)
        self.assertNotEqual(jspec["serviceAccountName"], spec["serviceAccountName"])
        self.assertEqual([e["name"] for e in jspec["containers"][0]["env"]], ["OPERATOR_DATABASE_URL"])
        self.assertEqual(jspec["containers"][0]["image"], lock["images"]["go"])

    def test_limits_health_startup_and_initial_traffic(self):
        service, _ = staging.render(*fixture())
        template = service["spec"]["template"]
        a = template["metadata"]["annotations"]
        self.assertEqual(json.loads(a["run.googleapis.com/container-dependencies"]), {"go": ["adk"], "adk": ["laya"]})
        self.assertEqual(a["autoscaling.knative.dev/maxScale"], "2")
        self.assertEqual(a["autoscaling.knative.dev/minScale"], "0")
        self.assertEqual(template["spec"]["timeoutSeconds"], 360)
        self.assertEqual(template["spec"]["containerConcurrency"], 10)
        self.assertEqual(service["spec"]["traffic"][0]["percent"], 100)
        for container in template["spec"]["containers"]:
            probe = container["startupProbe"]
            self.assertLessEqual(probe["periodSeconds"] * probe["failureThreshold"], 240)
            self.assertEqual(container["resources"]["limits"]["memory"], "4Gi" if container["name"] == "laya" else "512Mi")

    def test_candidate_preserves_known_good_traffic(self):
        c, lock = fixture()
        c["previous_revision"] = "prompt-shop-staging-good"
        service, _ = staging.render(c, lock)
        self.assertEqual([x["percent"] for x in service["spec"]["traffic"]], [0, 100])
        c["previous_revision"] = "prompt-shop-staging-test-123"
        with self.assertRaises(ValueError):
            staging.render(c, lock)

    def test_no_implicit_public_access_even_when_selected(self):
        c, lock = fixture()
        c["reviewer_access"] = "public"
        service, _ = staging.render(c, lock)
        self.assertEqual(service["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"], "false")
        self.assertNotIn("allUsers", json.dumps(staging.provision_commands(c)))

    def test_reject_incomplete_approval_and_invalid_configuration(self):
        for field, value in [("project_id", None), ("approved_by", ""), ("cleanup_date", "2000-01-01"),
                             ("reviewer_access", None), ("sql_tier", None), ("budget_amount", "0USD"),
                             ("sql_storage_gb", True), ("public_origin", "http://example.test"),
                             ("public_origin", "https://example.test/path")]:
            with self.subTest(field=field, value=value):
                c, lock = fixture()
                c[field] = value
                with self.assertRaises(ValueError):
                    staging.render(c, lock)

    def test_reject_mutable_images_and_secret_versions(self):
        c, lock = fixture()
        for field in ("go", "adk", "laya"):
            changed = copy.deepcopy(lock)
            changed["images"][field] = "example.test/image:latest"
            with self.assertRaises(ValueError):
                staging.render(c, changed)
        for version in ("latest", "0", 1, None):
            changed = copy.deepcopy(c)
            changed["secrets"]["database"]["version"] = version
            with self.assertRaises(ValueError):
                staging.render(changed, lock)

    def test_reject_secret_values_or_shared_secret_roles(self):
        c, lock = fixture()
        c["secrets"]["database"]["value"] = "must-not-enter-config"
        with self.assertRaises(ValueError):
            staging.render(c, lock)
        c, lock = fixture()
        c["secrets"]["operator-database"]["name"] = c["secrets"]["database"]["name"]
        with self.assertRaises(ValueError):
            staging.render(c, lock)
        c, lock = fixture()
        c["GOOGLE_API_KEY"] = "forbidden"
        with self.assertRaises(ValueError):
            staging.render(c, lock)

    def test_provision_plan_scopes_iam_and_durable_database(self):
        c, _ = fixture()
        commands = staging.provision_commands(c)
        sql = next(cmd for cmd in commands if cmd[1:4] == ["sql", "instances", "create"])
        self.assertIn("--connector-enforcement=REQUIRED", sql)
        self.assertIn("--deletion-protection", sql)
        self.assertIn("--enable-point-in-time-recovery", sql)
        self.assertFalse(any("authorized-networks" in arg for arg in sql))
        self.assertLess(next(i for i, cmd in enumerate(commands) if "budgets" in cmd), commands.index(sql))
        bindings = [cmd for cmd in commands if "--role=roles/secretmanager.secretAccessor" in cmd]
        self.assertEqual(len(bindings), 8)
        for cmd in bindings:
            expected = "operator" if "prompt-shop-operator-database" in cmd else "runtime"
            self.assertIn("--member=serviceAccount:" + staging.account(c, expected), cmd)
            self.assertNotIn("projects", cmd)


class ModelAndBuild(unittest.TestCase):
    def bundle(self, root):
        root.mkdir(parents=True, exist_ok=True)
        for name in ["LICENSE", "model.safetensors", "config.json"]:
            (root / name).write_text("offline fixture, not model weights")
        manifest = {"repository": "convaiinnovations/laya", "revision": "d" * 40,
                    "license": "Apache-2.0", "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}}
        (root / "manifest.json").write_text(json.dumps(manifest))

    def test_model_checksum_tampering_and_unlisted_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.bundle(root)
            verify(root)
            (root / "model.safetensors").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify(root)
            (root / "extra").write_text("unlisted")
            with self.assertRaisesRegex(ValueError, "exactly"):
                verify(root)

    def test_model_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.bundle(root)
            (root / "escape").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(ValueError, "symlink"):
                verify(root)

    def test_build_context_excludes_private_and_generated_inputs(self):
        for name in ["agent/.env", "web/.env.production", "agent/.venv/lib/x.py", "web/node_modules/x.js",
                     "references/monti-jarvis/key", "intent/model/credentials.json", "data/recording.wav",
                     "../agent/app.py", "/internal/a.go", "internal/a_test.go", "agent/tests/test_x.py"]:
            with self.subTest(name=name):
                self.assertFalse(build.allowed(name))
        for name in build.REQUIRED:
            self.assertTrue(build.allowed(name), name)

    def test_package_only_committed_allowed_files_and_missing_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout.decode().strip()
            git("init")
            git("config", "user.email", "offline@example.test")
            git("config", "user.name", "Offline test")
            (root / "README.md").write_text("fixture")
            git("add", ".")
            git("commit", "-m", "incomplete fixture")
            with self.assertRaisesRegex(ValueError, "integration build inputs missing"):
                build.package(root, git("rev-parse", "HEAD"), Path(tmp) / "missing")
            for name in build.REQUIRED:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("fixture")
            (root / "intent/model/manifest.json").unlink()
            self.bundle(root / "intent/model")
            (root / "agent/.env").write_text("FAKE_SECRET=excluded")
            git("add", ".")
            git("commit", "-m", "complete fixture")
            (root / "agent/uncommitted.py").write_text("excluded")
            destination = Path(tmp) / "context"
            build.package(root, git("rev-parse", "HEAD"), destination)
            self.assertFalse((destination / "agent/.env").exists())
            self.assertFalse((destination / "agent/uncommitted.py").exists())
            self.assertFalse((destination / "README.md").exists())
            self.assertTrue((destination / "Dockerfile").is_file())

    def test_build_commands_same_commit_digest_bases_and_platform(self):
        _, lock = fixture()
        plan = list(build.commands(lock, Path("/tmp/test context"), "asia-southeast1-docker.pkg.dev/unit-project/prompt-shop"))
        self.assertEqual(len(plan), 3)
        for cmd in plan:
            self.assertIn("--platform=linux/amd64", cmd)
            self.assertIn("org.opencontainers.image.revision=" + lock["source_commit"], cmd)
            self.assertNotIn("--push", cmd)


if __name__ == "__main__":
    unittest.main()
