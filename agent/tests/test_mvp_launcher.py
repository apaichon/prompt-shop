import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "scripts/mvp.py"


class LocalMVP(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location("local_mvp_test", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_configuration_preserves_provider_settings_and_separates_credentials(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "agent").mkdir()
            (root / "intent/local/model-bundle").mkdir(parents=True)
            (root / "intent/local/model-bundle/model.safetensors").write_bytes(b"fixture, never loaded")
            (root / "agent/.env").write_text("GOOGLE_API_KEY=synthetic-private-key\nGEMINI_MODEL=gemini-configured-live\nGEMINI_VOICE=Aoede\nADK_BRIDGE_SECRET=too-short\n")
            (root / ".env").write_text("PORT=8080\nPOSTGRES_PORT=55432\nSHOPPER_AUTH_ENABLED=false\n")
            with patch.object(module, "ROOT", root):
                go, agent, intent = module.configure()
            self.assertNotIn("GOOGLE_API_KEY", go)
            self.assertNotIn("GOOGLE_API_KEY", intent)
            self.assertEqual(agent["GOOGLE_API_KEY"], "synthetic-private-key")
            self.assertEqual((agent["GEMINI_MODEL"], agent["GEMINI_VOICE"]), ("gemini-configured-live", "Aoede"))
            self.assertEqual(agent["INTENT_BACKEND"], "embedding")
            self.assertEqual(go["INTENT_BACKEND"], "embedding")
            self.assertEqual(go["ADK_BRIDGE_SECRET"], agent["ADK_BRIDGE_SECRET"])
            self.assertGreaterEqual(len(agent["ADK_BRIDGE_SECRET"]), 32)
            self.assertEqual(intent["LAYA_INTERNAL_TOKEN"], agent["LAYA_INTERNAL_TOKEN"])
            self.assertEqual((root / "agent/.env").stat().st_mode & 0o077, 0)
            unscoped = {"GOOGLE_API_KEY": "synthetic-provider-key", "OPERATOR_DATABASE_URL": "synthetic-operator-url",
                        "DATABASE_URL": "synthetic-reader-url", "LAYA_INTERNAL_TOKEN": "synthetic-classifier-token"}
            for role in ("go", "adk", "laya"):
                scoped = module.service_env(role, unscoped)
                self.assertNotIn("OPERATOR_DATABASE_URL", scoped)
                self.assertEqual("GOOGLE_API_KEY" in scoped, role == "adk")
                self.assertEqual("DATABASE_URL" in scoped, role == "go")
                self.assertEqual(scoped.get("INTENT_BACKEND"), "embedding" if role in {"adk", "go"} else None)
            saved = module.service_env("adk", {"INTENT_BACKEND": "laya", "GOOGLE_API_KEY": "synthetic-provider-key"})
            self.assertEqual(saved.get("INTENT_BACKEND"), "laya")

    def test_stop_preserves_a_foreign_process_reusing_saved_pid(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "go.pid").write_text("12345\n")
            class Result:
                stdout = f"/usr/bin/unrelated-server --cwd {module.ROOT}\n"
            with patch.object(module, "RUN", path), patch.object(module.subprocess, "run", return_value=Result()), patch.object(module.os, "kill") as kill:
                with self.assertRaises(RuntimeError):
                    module.stop()
                kill.assert_not_called()


    def test_backend_services_only_start_laya_for_explicit_rollback(self):
        module = self.load()
        self.assertEqual(module.backend_services("embedding"), ("adk", "go"))
        self.assertEqual(module.backend_services("laya"), ("laya", "adk", "go"))
        with self.assertRaises(RuntimeError):
            module.backend_services("typo")
