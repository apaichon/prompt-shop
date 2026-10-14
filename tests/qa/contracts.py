"""Independent QA assertions; never imports the application's validators."""
from pathlib import Path
import hashlib
import json
import math
import re

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ID = re.compile(r"[a-z0-9-]{1,64}\Z")
THRESHOLDS = {"catalog_correct": 27, "catalog_trials": 30, "intent_correct": 36, "intent_trials": 40,
              "confidence": .70, "margin": .15, "actionable_audio_ms": 5000, "verified_card_ms": 8000,
              "typed_render_ms": 2000, "route_render_ms": 2000, "classification_ms": 1200}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def positive_int(value):
    return type(value) is int and value > 0


def load_frozen(directory=FIXTURES):
    freeze = json.loads((directory / "freeze.json").read_text())
    require(freeze["thresholds"] == THRESHOLDS and re.fullmatch(r"[0-9a-f]{40}", freeze["catalog_source_commit"]), "frozen thresholds/source identity differs")
    require(set(freeze["files"]) == {"catalog.json", "catalog-queries.json", "intent-queries.json"}, "frozen file inventory differs")
    for name, digest in freeze["files"].items():
        require(hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest, "frozen input hash differs: " + name)
    catalog = json.loads((directory / "catalog.json").read_text())
    queries = json.loads((directory / "catalog-queries.json").read_text())
    intents = json.loads((directory / "intent-queries.json").read_text())
    require(len(queries) == 30 and len({q["id"] for q in queries}) == 30, "catalog denominator must be 30 distinct cases")
    require(len(intents) == 40 and len({q["id"] for q in intents}) == 40, "intent denominator must be 40 distinct cases")
    for label in ("find_item", "select_item", "repeat_directions", "out_of_scope"):
        require(sum(q["expected_intent"] == label for q in intents) == 10, "intent corpus is not balanced")
    require(all(q["binding_status"] == ("bound" if q["expected_product_id"] is not None else "missing_from_seed") for q in queries), "inconsistent expected product binding")
    return freeze, catalog, queries, intents


class Authority:
    def __init__(self, catalog):
        self.catalog = catalog
        self.products = {p["id"]: p for p in catalog["products"]}
        self.shelves = {s["id"]: s for s in catalog["shelves"]}
        self.aisles = {a["id"]: a for a in catalog["aisles"]}
        self.nodes = {n["id"]: n for n in catalog["nodes"]}
        self.edges = {frozenset((e["from_node_id"], e["to_node_id"])): e["weight"] for e in catalog["edges"]}

    def product(self, value):
        require(isinstance(value, dict) and set(value) == {"id", "name", "category", "aisle", "shelf", "route_available"}, "product DTO fields differ")
        stored = self.products.get(value["id"])
        require(stored is not None and stored["state"] == "published", "unknown/inactive candidate")
        shelf = self.shelves[stored["shelf_id"]]
        aisle = self.aisles[shelf["aisle_id"]]
        require(value["name"] == stored["name"] and value["category"] == stored["category"], "product identity differs from authoritative fixture")
        require(value["aisle"] == {"id": aisle["id"], "label": aisle["label"]} and value["shelf"] == {"id": shelf["id"], "label": shelf["label"]}, "fabricated/stale location association")
        require(type(value["route_available"]) is bool, "route availability must be boolean")
        from .geometry import reachable
        connected = reachable(self.catalog["store"]["entrance_node_id"], self.catalog["edges"])
        require(value["route_available"] == (shelf["map_node_id"] in connected), "false route availability")
        return stored

    def search(self, value, query):
        require(isinstance(value, dict) and set(value) == {"query", "language", "catalog_version", "candidates", "ambiguous"}, "search DTO fields differ")
        require(value["query"] == query.strip() and value["language"] == "en-US" and positive_int(value["catalog_version"]), "search metadata differs")
        require(isinstance(value["candidates"], list) and len(value["candidates"]) <= 3 and type(value["ambiguous"]) is bool, "candidate cap/ambiguity invalid")
        ids = []
        for candidate in value["candidates"]:
            self.product(candidate)
            ids.append(candidate["id"])
        require(len(set(ids)) == len(ids), "duplicate candidates")
        if len(ids) > 1:
            require(value["ambiguous"], "multiple candidates require clarification")
        return ids

    def map(self, value):
        fields = {"store_id", "name", "map_version", "width", "height", "origin_node_id", "aisles", "nodes", "edges", "enabled_languages"}
        require(isinstance(value, dict) and set(value) == fields, "map DTO fields differ")
        source = self.catalog["store"]
        require(value["store_id"] == self.catalog["store_id"] and value["name"] == source["name"] and value["width"] == source["map_width"] and value["height"] == source["map_height"] and value["origin_node_id"] == source["entrance_node_id"], "map authority differs")
        require(positive_int(value["map_version"]) and value["enabled_languages"] == ["en-US"], "map version/language invalid")
        require(number(value["width"]) and number(value["height"]), "invalid map dimensions")
        require(all(number(n["x"]) and number(n["y"]) for n in value["nodes"]), "invalid node coordinates")
        require(all(number(p["x"]) and number(p["y"]) for a in value["aisles"] for p in a["polygon"]), "invalid polygon coordinates")
        require(sorted(value["aisles"], key=lambda a: a["id"]) == sorted(self.catalog["aisles"], key=lambda a: a["id"]), "obstacle geometry differs")
        require(sorted(value["nodes"], key=lambda a: a["id"]) == sorted(self.catalog["nodes"], key=lambda a: a["id"]), "node geometry differs")
        require(all(isinstance(e, dict) and set(e) == {"from", "to"} for e in value["edges"]), "edge fields differ")
        pairs = [frozenset((e["from"], e["to"])) for e in value["edges"]]
        require(len(pairs) == len(set(pairs)) and set(pairs) == set(self.edges), "walkable edges differ")

    def route(self, value, requested, public_map):
        fields = {"product", "catalog_version", "map_version", "origin_node_id", "node_ids", "points", "steps", "distance_units"}
        require(isinstance(value, dict) and set(value) == fields, "route DTO fields differ")
        product = self.product(value["product"])
        require(product["id"] == requested and positive_int(value["catalog_version"]) and positive_int(value["map_version"]) and value["map_version"] == public_map["map_version"], "wrong product/version route")
        shelf = self.shelves[product["shelf_id"]]
        require(shelf["map_node_id"] is not None, "unmapped shelf received a path")
        ids, points = value["node_ids"], value["points"]
        require(isinstance(ids, list) and isinstance(points, list) and all(isinstance(i, str) for i in ids) and 1 <= len(ids) <= 2048 and len(ids) == len(points) and len(set(ids)) == len(ids), "path is empty/cyclic or point count differs")
        origin = self.catalog["store"]["entrance_node_id"]
        require(value["origin_node_id"] == origin and ids[0] == origin and ids[-1] == shelf["map_node_id"], "wrong route endpoint")
        distance = 0
        from .geometry import crosses_interior
        for i, node_id in enumerate(ids):
            node = self.nodes.get(node_id)
            require(isinstance(points[i], dict) and set(points[i]) == {"x", "y"} and number(points[i]["x"]) and number(points[i]["y"]), "invalid path coordinate")
            require(node is not None and points[i] == {"x": node["x"], "y": node["y"]}, "invented path point")
            if i:
                edge = frozenset((ids[i-1], node_id))
                require(edge in self.edges, "non-walkable route segment")
                distance += self.edges[edge]
                require(not any(crosses_interior(points[i-1], points[i], a["polygon"]) for a in self.aisles.values()), "route crosses shelf interior")
        require(number(value["distance_units"]) and math.isclose(value["distance_units"], distance, rel_tol=1e-8, abs_tol=1e-8), "route distance differs from edge weights")
        require(isinstance(value["steps"], list) and 1 <= len(value["steps"]) <= 100 and all(isinstance(s, str) and s.strip() and len(s) <= 500 for s in value["steps"]), "text directions missing/invalid")
        labels = " ".join(value["steps"]).casefold()
        require(shelf["label"].casefold() in labels and self.aisles[shelf["aisle_id"]]["label"].casefold() in labels, "directions do not name stored destination")


def intent_contract(value, revision):
    fields = {"schema_version", "intent", "confidence", "margin", "abstained", "reason", "model_revision"}
    require(isinstance(value, dict) and set(value) == fields, "intent DTO fields differ")
    require(value["schema_version"] == "intent-v1" and value["model_revision"] == revision and re.fullmatch(r"[0-9a-f]{40}", revision or ""), "unqualified classifier identity")
    require(type(value["abstained"]) is bool, "abstention flag invalid")
    for key in ("confidence", "margin"):
        require(value[key] is None or number(value[key]) and 0 <= value[key] <= 1, "classifier score invalid")
    if value["abstained"]:
        require(value["intent"] is None and value["reason"] in ("low_confidence", "timeout", "busy", "error"), "unsafe abstention")
    else:
        require(value["intent"] in ("find_item", "select_item", "repeat_directions", "out_of_scope") and value["reason"] is None, "unknown intent")
        require(number(value["confidence"]) and value["confidence"] >= .70 and number(value["margin"]) and value["margin"] >= .15, "accepted below frozen thresholds")
