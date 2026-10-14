import hashlib
import json
from .contracts import Authority, ID, number
from .geometry import crosses_interior, reachable


def audit_fixture(catalog, queries):
    authority = Authority(catalog)
    errors = []
    for name in ("products", "shelves", "aisles", "nodes"):
        rows = catalog[name]
        if len(rows) != len({row["id"] for row in rows}) or not all(ID.fullmatch(row["id"]) for row in rows):
            errors.append("duplicate/invalid " + name + " IDs")
    published = [p for p in catalog["products"] if p["state"] == "published"]
    if catalog["store"]["entrance_node_id"] not in authority.nodes:
        errors.append("entrance node missing")
    pairs = [frozenset((e["from_node_id"], e["to_node_id"])) for e in catalog["edges"]]
    if len(pairs) != len(set(pairs)) or any(len(p) != 2 for p in pairs):
        errors.append("duplicate/reversed/self edges")
    if len(published) < 60 or len(catalog["aisles"]) < 8:
        errors.append("fixture requires at least 60 published products/eight aisles")
    for edge in catalog["edges"]:
        a, b = authority.nodes.get(edge["from_node_id"]), authority.nodes.get(edge["to_node_id"])
        if not a or not b or not number(edge["weight"]) or edge["weight"] <= 0:
            errors.append("invalid edge endpoint/weight")
            continue
        if any(crosses_interior(a, b, aisle["polygon"]) for aisle in catalog["aisles"]):
            errors.append("edge crosses obstacle: " + edge["from_node_id"] + "/" + edge["to_node_id"])
    connected = reachable(catalog["store"]["entrance_node_id"], catalog["edges"])
    destinations = []
    for product in published:
        shelf = authority.shelves.get(product["shelf_id"])
        valid = bool(shelf and shelf["aisle_id"] in authority.aisles and shelf["map_node_id"] in connected)
        if not valid:
            errors.append("unreachable/invalid destination: " + product["id"])
        destinations.append({"product_id": product["id"], "destination_node": shelf["map_node_id"] if shelf else None, "valid": valid})
    unbound = []
    for case in queries:
        expected = case["expected_product_id"]
        if expected is None or expected not in authority.products or authority.products[expected]["state"] != "published":
            unbound.append({"case_id": case["id"], "expected_label": case["expected_label"]})
    if unbound:
        errors.append("required canonical products are missing from the seed")
    return {"status": "pass" if not errors else "fail", "published_products": len(published), "aisles": len(catalog["aisles"]),
            "checked_edges": len(catalog["edges"]), "destinations": destinations, "unbound_cases": unbound, "errors": errors}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")
