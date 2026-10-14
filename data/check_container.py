"""TASK-0001 restart/permissions gate against an existing disposable test DB.
Prerequisites: prompt-shop-task1-db on localhost:55439, database prompt_shop_task1,
Go integration tests have seeded it; tmp/server is a static Linux arm64 binary.
This script creates/removes only the named task1 app containers. No cloud calls.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DB = "prompt-shop-task1-db"
APP = "prompt-shop-task1-app"
FULL = "prompt-shop-task1-full"
def run(args, **kwargs):
    return subprocess.run(["rtk", "proxy", *args], check=True, capture_output=True, text=True, **kwargs).stdout.strip()
def sql(statement):
    return run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "prompt_shop_task1", "-At", "-v", "ON_ERROR_STOP=1"], input=statement)
def snapshot():
    tables = ["stores", "aisles", "map_nodes", "map_edges", "shelves", "products", "product_aliases", "import_batches"]
    rows = [sql(f"SELECT COALESCE(jsonb_agg(v ORDER BY v::text),'[]'::jsonb) FROM (SELECT to_jsonb(t) v FROM {table} t) q;") for table in tables]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()
def http(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as response:
            return response.status, json.load(response), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error), dict(error.headers)
def wait_ready(port, expected):
    for _ in range(40):
        try:
            status, body, headers = http(port, "/readyz")
            if status == expected:
                return body, headers
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    raise AssertionError(f"readiness did not reach {expected}")

sql((ROOT / "migrations/roles.sql").read_text())
sql((ROOT / "migrations/local_roles.sql").read_text())
permissions = sql("""SELECT
 has_table_privilege('prompt_shop_public','products','SELECT'),
 has_table_privilege('prompt_shop_public','products','INSERT'),
 has_table_privilege('prompt_shop_public','voice_tickets','SELECT'),
 has_table_privilege('prompt_shop_backoffice','products','UPDATE'),
 has_table_privilege('prompt_shop_backoffice','map_nodes','UPDATE'),
 has_column_privilege('prompt_shop_backoffice','stores','catalog_version','UPDATE'),
 has_column_privilege('prompt_shop_backoffice','stores','map_version','UPDATE'),
 has_table_privilege('prompt_shop_voice','voice_tickets','UPDATE'),
 has_table_privilege('prompt_shop_voice','products','SELECT'),
 has_schema_privilege('prompt_shop_public','public','CREATE');""")
assert permissions == "t|f|f|t|f|t|f|t|f|f", permissions
print("PASS: public/backoffice/voice role privilege boundaries")
# Verify the read-only LOGIN cannot mutate, rather than checking grants alone.
result = subprocess.run(["rtk", "proxy", "docker", "exec", "-e", "PGPASSWORD=local-reader-only", DB, "psql", "-h", "127.0.0.1", "-U", "prompt_shop_reader", "-d", "prompt_shop_task1", "-v", "ON_ERROR_STOP=1", "-c", "UPDATE products SET name='must fail'"], capture_output=True, text=True)
assert result.returncode != 0 and "permission denied" in result.stderr, "reader mutation was not rejected"
print("PASS: actual reader UPDATE rejected")
context = ROOT / "tmp"
(context / "Dockerfile.smoke").write_text("FROM scratch\nCOPY server /server\nUSER 65532:65532\nENTRYPOINT [\"/server\"]\n")
run(["docker", "build", "-f", str(context / "Dockerfile.smoke"), "-t", "prompt-shop-task1-smoke:local", str(context)])
url = "postgres://prompt_shop_reader:local-reader-only@host.docker.internal:55439/prompt_shop_task1?sslmode=disable"
created = []
try:
    for name, mode, port in [(APP, "foundation", 18089), (FULL, "full", 18090)]:
        run(["docker", "run", "-d", "--rm", "--name", name, "-e", "DATABASE_URL=" + url, "-e", "READINESS_MODE=" + mode, "-p", f"127.0.0.1:{port}:8080", "prompt-shop-task1-smoke:local"])
        created.append(name)
    body, headers = wait_ready(18089, 200)
    assert body == {"status": "ready"} and headers.get("X-Readiness-Scope") == "foundation"
    assert http(18089, "/healthz")[0] == 200
    assert http(18089, "/api/search")[0] == 404
    assert http(18089, "/internal/tools/search_catalog")[0] == 404
    assert wait_ready(18090, 503)[0] == {"status": "not_ready"}
    print("PASS: local foundation ready; missing ADK/Laya keeps full readiness 503; private routes absent")
    sql("UPDATE products SET state='archived' WHERE id='red-apples';")
    wait_ready(18089, 200)
    sql("UPDATE products SET state='published' WHERE id='red-apples';")
    print("PASS: legitimate catalog archive does not incorrectly fail readiness")
    before = snapshot()
    run(["docker", "restart", APP])
    wait_ready(18089, 200)
    after = snapshot()
    assert before == after
    print("PASS: app container restart preserves complete DB snapshot " + before)
    run(["docker", "stop", DB])
    assert wait_ready(18089, 503)[0] == {"status": "not_ready"}
    assert http(18089, "/healthz")[0] == 200
    run(["docker", "start", DB])
    wait_ready(18089, 200)
    assert snapshot() == before
    print("PASS: DB outage gives readyz 503 / healthz 200; named-volume restart preserves all rows")
    print("DB counts: " + sql("SELECT (SELECT count(*) FROM products WHERE state='published'),(SELECT count(*) FROM aisles),(SELECT count(*) FROM product_aliases);"))
finally:
    for name in created:
        subprocess.run(["rtk", "proxy", "docker", "stop", name], capture_output=True)
