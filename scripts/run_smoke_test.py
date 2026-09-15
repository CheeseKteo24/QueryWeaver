from __future__ import annotations

import argparse
import json
import urllib.request


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"GET {url} returned HTTP {response.status}")
        return response.read().decode()


def post_query(base_url: str) -> dict[str, object]:
    body = json.dumps({"question": "按地区统计销售额", "top_k": 3}).encode()
    request = urllib.request.Request(
        f"{base_url}/v1/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"POST /v1/query returned HTTP {response.status}")
        payload: dict[str, object] = json.load(response)
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a running QueryWeaver service")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    health = json.loads(fetch_text(f"{base_url}/health"))
    if health.get("status") != "ok":
        raise SystemExit(f"unexpected health response: {health}")

    page = fetch_text(f"{base_url}/")
    if "QueryWeaver" not in page or "/app.js" not in page:
        raise SystemExit("browser shell is missing expected assets")

    payload = post_query(base_url)
    if payload.get("route") != "sql":
        raise SystemExit(f"unexpected route: {payload.get('route')}")
    sql_result = payload.get("sql_result")
    if not isinstance(sql_result, dict) or not sql_result.get("rows"):
        raise SystemExit("SQL result rows are missing")
    if not str(payload.get("validated_sql", "")).startswith("SELECT"):
        raise SystemExit("validated SELECT is missing")

    print("Smoke test passed: health, browser shell, routing, validation, and SQL result")


if __name__ == "__main__":
    main()
