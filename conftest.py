"""Shared fixtures and the golden-file assertion engine for the ptdata correctness suite.

Each YAML file under cases/ is a self-contained golden file: it names a tool, the request
parameters, a provenance note, and a list of expectations. Tests are data-driven — adding a
new edge case is a new YAML file, no code change. PRs with new cases are welcome.

Configuration (env vars):
  PTDATA_BASE_URL   base URL of the service under test (default http://localhost:8000)
  PTDATA_API_KEY    API key, if the service requires one
"""
from __future__ import annotations

import os
import pathlib
import httpx
import pytest
import yaml

CASES_DIR = pathlib.Path(__file__).parent / "cases"

# Map the logical tool name in a golden file to its REST endpoint under /v1/.
TOOL_ENDPOINTS = {
    "get_fundamentals": "/v1/fundamentals",
    "get_price_history": "/v1/prices",
    "get_index_constituents": "/v1/index-constituents",
    "get_corporate_actions": "/v1/corporate-actions",
    "get_filing_metadata": "/v1/filings",
    "get_earnings_event": "/v1/earnings-event",
    "get_implied_expectation": "/v1/implied-expectation",
}


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("PTDATA_BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="session")
def client(base_url):
    headers = {}
    if key := os.environ.get("PTDATA_API_KEY"):
        headers["Authorization"] = f"Bearer {key}"
    with httpx.Client(base_url=base_url, headers=headers, timeout=30.0) as c:
        yield c


def load_cases(category: str) -> list[dict]:
    """Load every YAML golden file in cases/<category>/, sorted by filename."""
    d = CASES_DIR / category
    cases = []
    for path in sorted(d.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        data["_file"] = path.name
        cases.append(data)
    return cases


def call(client: httpx.Client, case: dict):
    """Issue the request described by a golden file and return the parsed JSON response.

    Fails with a clear message when the service is unreachable or has not implemented the
    endpoint yet (HTTP 501) — these are the expected red states before implementation.
    """
    tool = case["tool"]
    endpoint = TOOL_ENDPOINTS.get(tool)
    if endpoint is None:
        pytest.fail(f"Unknown tool {tool!r} in {case.get('_file')}")
    try:
        resp = client.get(endpoint, params=case.get("request", {}))
    except httpx.ConnectError as e:
        pytest.fail(f"Service unreachable ({e}). Set PTDATA_BASE_URL or start the dev server.")
    if resp.status_code == 501:
        pytest.fail(f"NOT IMPLEMENTED: {tool} ({endpoint}) returned 501 — spec not yet satisfied.")
    if resp.status_code >= 400:
        pytest.fail(f"{tool} ({endpoint}) returned HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _resolve(obj, path: str):
    """Resolve a dotted path (with [i] index support) into a nested JSON object."""
    cur = obj
    for part in path.split("."):
        if "[" in part:
            name, idx = part[:-1].split("[")
            if name:
                cur = cur[name]
            cur = cur[int(idx)]
        else:
            cur = cur[part]
    return cur


def check_expectations(response: dict, case: dict):
    """Apply each expectation in a golden file against the response."""
    for exp in case.get("expect", []):
        path, op = exp["path"], exp["op"]
        label = f"[{case['_file']}] {path} {op}"
        try:
            actual = _resolve(response, path) if op not in ("exists", "absent") else None
        except (KeyError, IndexError, TypeError):
            if op == "absent":
                continue
            pytest.fail(f"{label}: path not found in response")

        if op == "exists":
            try:
                value = _resolve(response, path)
            except (KeyError, IndexError, TypeError):
                pytest.fail(f"{label}: expected present, was missing")
            if value is None:
                pytest.fail(f"{label}: expected present and non-null, was null")
        elif op == "absent":
            try:
                _resolve(response, path)
                pytest.fail(f"{label}: expected absent, was present")
            except (KeyError, IndexError, TypeError):
                pass
        elif op == "eq":
            assert actual == exp["value"], f"{label}: expected {exp['value']!r}, got {actual!r}"
        elif op == "approx":
            tol = exp.get("tol", 0.01)
            target = float(exp["value"])
            assert abs(float(actual) - target) <= abs(target) * tol, \
                f"{label}: {actual} not within {tol:.0%} of {target}"
        elif op == "lt":
            assert float(actual) < float(exp["value"]), f"{label}: {actual} !< {exp['value']}"
        elif op == "gt":
            assert float(actual) > float(exp["value"]), f"{label}: {actual} !> {exp['value']}"
        elif op == "contains":
            assert exp["value"] in actual, f"{label}: {exp['value']!r} not in {actual!r}"
        elif op == "not_contains":
            assert exp["value"] not in actual, f"{label}: {exp['value']!r} unexpectedly in {actual!r}"
        else:
            pytest.fail(f"{label}: unknown op {op!r}")

    # Lineage is mandatory in every response per methodology commitment #3.
    if case.get("lineage_required"):
        assert "lineage" in response, f"[{case['_file']}] response missing required lineage block"


def _cross(responses: list, spec: dict, file: str):
    """A cross-step assertion: compare a path in one response against another (or a literal).

    `left` / `right` are "<step_index>.<dotted.path>"; a bare value in `right` is a literal.
    """
    def side(ref):
        if isinstance(ref, str):
            head = ref.split(".", 1)[0]
            if head.isdigit():                      # "<step>.<path>"
                idx, path = ref.split(".", 1)
                return _resolve(responses[int(idx)], path)
            try:                                    # bare "<path>" -> single/first response
                return _resolve(responses[0], ref)
            except (KeyError, IndexError, TypeError):
                return ref                          # treat as a literal
        return ref
    l, r, op = side(spec["left"]), side(spec["right"]), spec["op"]
    label = f"[{file}] cross {spec['left']} {op} {spec['right']}"
    if op == "ne":
        assert l != r, f"{label}: both were {l!r}"
    elif op == "eq":
        assert l == r, f"{label}: {l!r} != {r!r}"
    elif op == "gt":
        assert float(l) > float(r), f"{label}: {l} !> {r}"
    elif op == "lt":
        assert float(l) < float(r), f"{label}: {l} !< {r}"
    else:
        pytest.fail(f"{label}: unknown cross op {op!r}")


def run_case(client: httpx.Client, case: dict):
    """Run a golden file: a single request, or a multi-step case with cross-step assertions.

    A case with a top-level `skip:` field is skipped with that reason (used for cases that are
    out of the current product scope — documented, not silently failing).

    Multi-step form (for point-in-time divergence demos): `steps` is a list of {request,
    expect}; an optional `cross` list compares paths across the collected step responses.
    """
    if case.get("skip"):
        pytest.skip(case["skip"])
    if "steps" in case:
        responses = []
        for i, step in enumerate(case["steps"]):
            sub = {"tool": case["tool"], "_file": f"{case['_file']}#step{i}", **step}
            resp = call(client, sub)
            responses.append(resp)
            check_expectations(resp, sub)
        for spec in case.get("cross", []):
            _cross(responses, spec, case["_file"])
    else:
        resp = call(client, case)
        check_expectations(resp, case)
        for spec in case.get("cross", []):
            _cross([resp], spec, case["_file"])
