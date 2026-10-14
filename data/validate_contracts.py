"""Validate TASK-0001 seed and wire examples; requires jsonschema 4.x."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads((ROOT / path).read_text())
def validate(schema, value):
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(value)

spec = read("api/openapi.yaml")  # JSON is also valid YAML 1.2.
assert spec["openapi"] == "3.1.0"
schemas = spec["components"]["schemas"]
for name, schema in schemas.items():
    Draft202012Validator.check_schema({**schema, "components": spec["components"]})
for filename, name in read("data/contracts/manifest.json").items():
    validate({**schemas[name], "components": spec["components"]}, read("data/contracts/" + filename))
validate(read("data/import.schema.json"), read("data/demo-store.json"))
live = read("data/contracts/live.schema.json")
for event in read("data/contracts/live-events.json"):
    validate(live, event)
private = read("data/contracts/private.schema.json")
for name, example in read("data/contracts/private-examples.json").items():
    validate({**private, "$ref": "#/$defs/" + name}, example)
# Every public operation has a meaningful response and all local refs resolve.
def refs(value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for child in value.values():
            yield from refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs(child)
for target in refs(spec):
    assert target.startswith("#/components/schemas/")
    assert target.rsplit("/", 1)[-1] in schemas, target
for path, methods in spec["paths"].items():
    for method, operation in methods.items():
        assert operation["responses"] and operation["operationId"], (path, method)
print(f"PASS: import schema/seed, {len(schemas)} API schemas, public examples, live events and private examples")
