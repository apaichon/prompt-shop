import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.qa.audit import audit_fixture
from tests.qa.contracts import Authority, FIXTURES, intent_contract, load_frozen
from tests.qa.geometry import crosses_interior
from tests.qa.http import Client, Response
from tests.qa.collector import collect_catalog, collect_anonymous
from tests.qa.measurements import assess_series, assess_voice, assess_intent, distribution
from tests.qa.report import template, release_report, measured_evidence

FREEZE, CATALOG, QUERIES, INTENTS = load_frozen()


def product_dto(product_id="milk-whole-1l"):
    authority = Authority(CATALOG)
    product = authority.products[product_id]
    shelf = authority.shelves[product["shelf_id"]]
    aisle = authority.aisles[shelf["aisle_id"]]
    return {"id": product_id, "name": product["name"], "category": product["category"],
            "aisle": {"id": aisle["id"], "label": aisle["label"]},
            "shelf": {"id": shelf["id"], "label": shelf["label"]}, "route_available": True}


def series():
    return [{"id": q["id"], "suite": "warm_normal", "status": "completed", "duration_ms": 100} for q in QUERIES]


class FrozenTests(unittest.TestCase):
    def test_frozen_source_inventory(self):
        self.assertEqual((len(QUERIES), len(INTENTS)), (30, 40))
        self.assertEqual(sum(p["state"] == "published" for p in CATALOG["products"]), 60)

    def test_mutation_requires_refreeze(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for file in FIXTURES.iterdir():
                if file.is_file():
                    (path/file.name).write_bytes(file.read_bytes())
            (path/"catalog-queries.json").write_text("[]")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                load_frozen(path)

    def test_seed_gaps_are_not_substituted(self):
        result = audit_fixture(CATALOG, QUERIES)
        self.assertEqual(result["status"], "fail")
        self.assertEqual({r["expected_label"] for r in result["unbound_cases"]}, {"Skimmed milk", "Plain yogurt", "Canned chickpeas"})
        self.assertEqual(len(result["destinations"]), 60)
        self.assertTrue(all(r["valid"] for r in result["destinations"]))

    def test_disconnected_destination_detected(self):
        data = copy.deepcopy(CATALOG)
        data["shelves"][0]["map_node_id"] = "missing-node"
        self.assertTrue(any("unreachable" in e for e in audit_fixture(data, QUERIES)["errors"]))

    def test_reverse_duplicate_edge_detected(self):
        data = copy.deepcopy(CATALOG)
        edge = dict(data["edges"][0])
        edge["from_node_id"], edge["to_node_id"] = edge["to_node_id"], edge["from_node_id"]
        data["edges"].append(edge)
        self.assertIn("duplicate/reversed/self edges", audit_fixture(data, QUERIES)["errors"])


class GeometryTests(unittest.TestCase):
    def polygon(self, points):
        return [{"x": x, "y": y} for x, y in points]

    def segment(self, a, b, polygon):
        return crosses_interior({"x": a[0], "y": a[1]}, {"x": b[0], "y": b[1]}, self.polygon(polygon))

    def test_boundary_allowed_interior_rejected(self):
        square = [(0, 0), (2, 0), (2, 2), (0, 2)]
        self.assertFalse(self.segment((-1, 0), (3, 0), square))
        self.assertTrue(self.segment((-1, 1), (3, 1), square))
        self.assertTrue(self.segment((1, 1), (3, 1), square))

    def test_narrow_obstacle_not_missed_by_midpoint(self):
        self.assertTrue(self.segment((0, 0), (100, 0), [(1, -.01), (1.001, -.01), (1.001, .01), (1, .01)]))

    def test_concave_and_vertex_touch(self):
        concave = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
        self.assertFalse(self.segment((2, 2), (4, 2), concave))
        self.assertTrue(self.segment((-1, 2), (4, 2), concave))
        self.assertFalse(self.segment((-1, 1), (1, -1), [(0, 0), (2, 0), (2, 2), (0, 2)]))


class ContractTests(unittest.TestCase):
    def public_map(self):
        source = CATALOG["store"]
        return {"store_id": CATALOG["store_id"], "name": source["name"], "map_version": 1,
                "width": source["map_width"], "height": source["map_height"], "origin_node_id": source["entrance_node_id"],
                "aisles": copy.deepcopy(CATALOG["aisles"]), "nodes": copy.deepcopy(CATALOG["nodes"]),
                "edges": [{"from": e["from_node_id"], "to": e["to_node_id"]} for e in CATALOG["edges"]], "enabled_languages": ["en-US"]}

    def route(self):
        oracle = Authority(CATALOG)
        shelf = oracle.shelves[oracle.products["milk-whole-1l"]["shelf_id"]]
        paths, pending = {"entrance": ["entrance"]}, ["entrance"]
        while pending:
            node = pending.pop(0)
            for pair in oracle.edges:
                if node in pair:
                    other = next(iter(pair-{node}))
                    if other not in paths:
                        paths[other] = paths[node]+[other]
                        pending.append(other)
        ids = paths[shelf["map_node_id"]]
        return {"product": product_dto(), "catalog_version": 1, "map_version": 1, "origin_node_id": "entrance", "node_ids": ids,
                "points": [{"x": oracle.nodes[i]["x"], "y": oracle.nodes[i]["y"]} for i in ids],
                "steps": [oracle.aisles[shelf["aisle_id"]]["label"]+" "+shelf["label"]],
                "distance_units": sum(oracle.edges[frozenset((a, b))] for a, b in zip(ids, ids[1:]))}

    def test_stored_map_and_route_pass(self):
        oracle = Authority(CATALOG)
        oracle.map(self.public_map())
        oracle.route(self.route(), "milk-whole-1l", self.public_map())

    def test_wrong_endpoint_nonedge_distance_and_map_version_rejected(self):
        for mode in ("endpoint", "nonedge", "distance", "version", "point", "labels"):
            route = self.route()
            if mode == "endpoint": route["node_ids"][-1] = "entrance"
            if mode == "nonedge": route["node_ids"], route["points"] = route["node_ids"][::len(route["node_ids"])-1], route["points"][::len(route["points"])-1]
            if mode == "distance": route["distance_units"] += 1
            if mode == "version": route["map_version"] = 2
            if mode == "point": route["points"][0]["x"] = True
            if mode == "labels": route["steps"] = ["Go somewhere"]
            with self.assertRaises(ValueError): Authority(CATALOG).route(route, "milk-whole-1l", self.public_map())

    def test_invented_obstacle_edge_extra_fields_rejected(self):
        for mode in ("obstacle", "node", "edge"):
            public_map = self.public_map()
            if mode == "obstacle": public_map["aisles"][0]["polygon"][0]["x"] += 1
            if mode == "node": public_map["nodes"][0]["x"] = True
            if mode == "edge": public_map["edges"][0]["admin"] = True
            with self.assertRaises(ValueError): Authority(CATALOG).map(public_map)

    def test_exact_stored_product_passes(self):
        Authority(CATALOG).product(product_dto())

    def test_wrong_location_and_route_flag_rejected(self):
        for change in ({"shelf": {"id": "invented", "label": "Shelf 99"}}, {"route_available": False}, {"name": "Invented milk"}):
            dto = product_dto()
            dto.update(change)
            with self.assertRaises(ValueError):
                Authority(CATALOG).product(dto)

    def test_unknown_or_draft_product_rejected(self):
        dto = product_dto()
        dto["id"] = next(p["id"] for p in CATALOG["products"] if p["state"] != "published")
        with self.assertRaises(ValueError):
            Authority(CATALOG).product(dto)

    def test_duplicate_and_missing_ambiguity_rejected(self):
        value = {"query": "milk", "language": "en-US", "catalog_version": 1, "ambiguous": True, "candidates": [product_dto(), product_dto()]}
        with self.assertRaises(ValueError):
            Authority(CATALOG).search(value, "milk")
        value["candidates"][1] = product_dto("milk-oat-1l")
        value["ambiguous"] = False
        with self.assertRaises(ValueError):
            Authority(CATALOG).search(value, "milk")

    def test_bool_version_rejected(self):
        with self.assertRaises(ValueError):
            Authority(CATALOG).search({"query": "milk", "language": "en-US", "catalog_version": True, "ambiguous": False, "candidates": []}, "milk")

    def test_low_confidence_and_unknown_revision_rejected(self):
        valid = {"schema_version": "intent-v1", "intent": "find_item", "confidence": .9, "margin": .5, "abstained": False, "reason": None, "model_revision": "a"*40}
        intent_contract(valid, "a"*40)
        for change in ({"confidence": .69}, {"margin": .14}, {"intent": "admin_write"}, {"model_revision": "latest"}, {"confidence": True}):
            value = dict(valid, **change)
            with self.assertRaises(ValueError):
                intent_contract(value, "a"*40)


class MeasurementTests(unittest.TestCase):
    def test_nearest_rank_p95(self):
        self.assertEqual(distribution(list(range(1, 31)))["p95_ms"], 29)
        self.assertEqual(distribution([])["p95_ms"], None)

    def test_failed_trial_cannot_be_dropped(self):
        rows = series()
        rows[0].update(status="failed", duration_ms=None)
        result = assess_series(rows, [q["id"] for q in QUERIES], 2000)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["trials"], 30)
        self.assertEqual(result["percentile_scope"], "completed_only_not_acceptance")

    def test_duplicate_missing_cold_nonfinite_rejected(self):
        ids = [q["id"] for q in QUERIES]
        for mode in ("duplicate", "missing", "cold"):
            rows = series()
            if mode == "duplicate": rows[0] = dict(rows[1])
            if mode == "missing": rows.pop()
            if mode == "cold": rows[0]["suite"] = "cold"
            with self.assertRaises(ValueError): assess_series(rows, ids, 2000)
        rows = series()
        rows[0]["duration_ms"] = float("nan")
        self.assertEqual(assess_series(rows, ids, 2000)["status"], "fail")

    def voice(self):
        return [{"id": q["id"], "suite": "warm_normal", "status": "completed", "last_voiced_sample_ms": 100,
                 "speech_end_source": "client_capture_clock_qa_vad", "first_actionable_audible_ms": 200,
                 "first_verified_card_render_ms": 300, "candidate_ids": [q["expected_product_id"]] if q["expected_product_id"] else [],
                 "heard_complete_answer": True, "spoken_locations_match_tools": True, "ui_locations_match_tools": True,
                 "native_audio_observed": True, "real_laya_before_catalog": True} for q in QUERIES]

    def test_filler_or_server_speech_end_is_not_audio_acceptance(self):
        rows = self.voice()
        rows[0]["speech_end_source"] = "server_caption"
        with self.assertRaises(ValueError): assess_voice(rows, QUERIES)
        rows = self.voice()
        rows[0]["first_actionable_audible_ms"] = None
        result = assess_voice(rows, QUERIES)
        self.assertEqual(result["actionable_audio"]["status"], "fail")

    def test_mock_audio_and_fixture_gaps_fail_voice(self):
        rows = self.voice()
        rows[0]["native_audio_observed"] = False
        result = assess_voice(rows, QUERIES)
        self.assertEqual(result["correct"], 27)
        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["complete_expected_bindings"])
        self.assertEqual(result["native_or_classification_failures"], [rows[0]["id"]])

    def test_invented_voice_candidate_rejected(self):
        rows = self.voice()
        rows[0]["candidate_ids"].append("invented-item")
        with self.assertRaises(ValueError): assess_voice(rows, QUERIES)

    def intent(self):
        return [{"id": q["id"], "suite": "warm_normal", "status": "completed", "duration_ms": 100,
                 "real_checkpoint_observed": True, "adk_classify_intent_observed": True,
                 "result": {"schema_version": "intent-v1", "intent": q["expected_intent"], "confidence": .9, "margin": .5,
                            "abstained": False, "reason": None, "model_revision": "a"*40}} for q in INTENTS]

    def test_intent_confusion_and_abstention_denominator(self):
        rows = self.intent()
        rows[0]["result"].update(intent=None, confidence=None, margin=None, abstained=True, reason="error")
        result = assess_intent(rows, INTENTS, "a"*40)
        self.assertEqual((result["trials"], result["correct"], result["coverage"]), (40, 39, .975))
        self.assertEqual(result["confusion"][INTENTS[0]["expected_intent"]]["abstention_or_error"], 1)

    def test_mock_classifier_and_deadline_fail(self):
        for field, value in (("real_checkpoint_observed", False), ("adk_classify_intent_observed", False), ("duration_ms", 1201)):
            rows = self.intent()
            rows[0][field] = value
            self.assertEqual(assess_intent(rows, INTENTS, "a"*40)["status"], "fail")


class ReleaseTests(unittest.TestCase):
    def test_model_evidence_must_match_the_operator_selected_model(self):
        observations = template(FREEZE)
        observations["candidate"].update(environment="deployed", origin="https://shop.example", commit="a"*40,
            deployment_id="fixture", measured_at="2026-10-16", device="test", network="test",
            native_model="gemini-3.9-live-fixture", laya_revision="b"*40)
        provenance = "deployed candidate/model/checkpoint/device/network provenance missing"
        selected = release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations, expected_model="models/gemini-3.9-live-fixture")
        self.assertNotIn(provenance, selected["blockers"])
        self.assertEqual(selected["recommendation"], "BLOCK_RELEASE")  # Other missing gates stay required.
        self.assertIn(provenance, release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations)["blockers"])

    def test_nonobject_and_mixed_cold_evidence_rejected(self):
        with self.assertRaises(ValueError): measured_evidence([], QUERIES, INTENTS)
        observations = template(FREEZE)
        observations["typed_render"] = ["invalid-row"]
        self.assertEqual(measured_evidence(observations, QUERIES, INTENTS)["typed_render"]["status"], "blocked")
        observations["cold_and_faults"] = [{"id": "catalog-01", "suite": "warm_normal", "status": "failed", "duration_ms": 99999}]
        self.assertIn("separate cold/fault observations missing", release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations)["blockers"])

    def test_empty_template_blocks_all_measurements(self):
        result = measured_evidence(template(FREEZE), QUERIES, INTENTS)
        self.assertTrue(all(v["status"] == "blocked" for v in result.values()))

    def test_local_fixture_cannot_qualify_release(self):
        observations = template(FREEZE)
        observations["candidate"].update(environment="deployed", origin="https://127.0.0.1:4194", commit="a"*40,
            deployment_id="fixture", measured_at="2026-10-14", device="test", network="test", native_model="gemini-3.8-live", laya_revision="b"*40)
        result = release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations)
        self.assertEqual(result["recommendation"], "BLOCK_RELEASE")
        self.assertIn("deployed candidate/model/checkpoint/device/network provenance missing", result["blockers"])

    def test_hash_or_candidate_drift_blocks_release(self):
        observations = template(FREEZE)
        observations["frozen_inputs"] = {}
        result = release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations, {"environment": "deployed", "origin": "https://shop.example"})
        self.assertIn("observation schema/frozen input identity differs", result["blockers"])
        self.assertIn("HTTP probes do not belong to the same deployed candidate and frozen inputs", result["blockers"])

    def test_manual_check_requires_hash_artifact_and_owner(self):
        observations = template(FREEZE)
        observations["candidate"]["commit"] = "a"*40
        check = observations["manual_checks"]["import_atomicity"]
        check.update(status="pass", reviewer="QA", candidate_commit="a"*40, artifact="import.md", sha256="0"*64)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/"import.md").write_text("redacted evidence")
            result = release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations, artifact_directory=path)
            self.assertEqual(result["manual_checks"]["import_atomicity"]["status"], "blocked")
            check["sha256"] = hashlib.sha256((path/"import.md").read_bytes()).hexdigest()
            result = release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations, artifact_directory=path)
            self.assertEqual(result["manual_checks"]["import_atomicity"]["status"], "pass")
            check["artifact"] = "../import.md"
            self.assertEqual(release_report(FREEZE, CATALOG, QUERIES, INTENTS, observations, artifact_directory=path)["manual_checks"]["import_atomicity"]["status"], "blocked")


class HTTPTests(unittest.TestCase):
    def test_redirect_and_cookie_values_are_not_returned(self):
        paths = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                paths.append(self.path)
                self.send_response(302 if self.path == "/redirect" else 200)
                self.send_header("Location", "/must-not-follow")
                self.send_header("Set-Cookie", "__Host-maintainer=secret-cookie-value; Secure; HttpOnly; SameSite=Strict; Path=/")
                self.send_header("Retry-After", "secret-header-value")
                self.send_header("X-Request-ID", "unsafe/header")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            client = Client("http://127.0.0.1:"+str(server.server_port), local=True, pace=0)
            response = client.request("GET", "/redirect")
            self.assertEqual(response.status, 302)
            self.assertEqual(paths, ["/redirect"])
            self.assertEqual(response.headers, {"request_id": "", "retry_after": ""})
            attrs = client.cookie_attributes("__Host-maintainer")
            self.assertNotIn("value", attrs)
            self.assertTrue(attrs["http_only"] and attrs["secure"] and attrs["host_only"])
            self.assertEqual(attrs["same_site"], "Strict")
            server.shutdown()
            thread.join()

    def test_insecure_remote_or_credentials_rejected(self):
        for url, options in (("http://shop.example", {}), ("https://user:password@shop.example", {}),
                             ("https://shop.example", {"local": True, "insecure_tls": True}),
                             ("https://shop.example", {"pace": 0})):
            with self.assertRaises(ValueError): Client(url, **options)
        Client("http://127.0.0.1:9999", local=True, pace=0)

    def test_fixed_origin_rejects_protocol_relative_target(self):
        with self.assertRaises(ValueError):
            Client("http://localhost:9999", local=True, pace=0).request("GET", "//other.example")

    def test_unavailable_endpoints_retain_all_thirty_misses(self):
        class Missing:
            def request(self, *args): return Response(404, {"error": {"code": "NOT_FOUND"}}, {}, 1)
        result = collect_catalog(Missing(), CATALOG, QUERIES)
        self.assertEqual((result["trials"], result["correct"], len(result["results"])), (30, 0, 30))
        self.assertEqual(result["status"], "fail")

    def test_denial_collector_never_uses_valid_credentials(self):
        calls = []
        class Denied:
            def request(self, method, path, body=None, headers=None):
                calls.append((method, path, body, headers))
                if path in ("/classify", "/internal/tools/search_catalog", "/internal/tools/get_product_route"):
                    return Response(404, {"error": {"code": "NOT_FOUND"}}, {}, 1)
                if headers and headers.get("Origin") == "https://untrusted.invalid":
                    return Response(403, {"error": {"code": "FORBIDDEN"}}, {}, 1)
                return Response(401, {"error": {"code": "AUTH_REQUIRED"}}, {}, 1)
        result = collect_anonymous(Denied())
        self.assertEqual(len(calls), 20)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(all(body in (None, {}, {"password": "not-a-real-password"}) for _, _, body, _ in calls))


if __name__ == "__main__":
    unittest.main()
