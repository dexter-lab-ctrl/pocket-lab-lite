"""Bounded historical OPA module observation from the release review child.

This is not activation proof, a replacement supervisor, or an authorization
decision. No mutation, policy evaluation or GET-route runtime probe occurs.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import urllib.request

from .lite_lifecycle_contract import canonical_bytes
from .lite_policy_compatibility import REGISTERED_MODULES

MAX_RESPONSE = 2 * 1024 * 1024
MAX_MODULES = 32


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("policy_observation_redirect")


def _get(path):
    from . import lite_policy_opa as opa
    if not opa._opa_endpoint_is_loopback():
        raise ValueError("policy_endpoint_not_loopback")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    request = urllib.request.Request(opa.OPA_BASE_URL + path, headers={"Accept": "application/json"})
    with opener.open(request, timeout=2) as response:
        raw = response.read(MAX_RESPONSE + 1)
        if response.status != 200 or len(raw) > MAX_RESPONSE:
            raise ValueError("policy_observation_unavailable")
    return json.loads(raw)["result"]


def compare_loaded_modules(manifest, modules):
    """OPA IDs are not filenames. Compare exact raw-byte digest multiplicities."""
    rows = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(rows, list) or not isinstance(modules, list) or len(modules) > MAX_MODULES:
        raise ValueError("policy_observation_invalid")
    expected_names = {p.rsplit("/", 1)[-1] for p in REGISTERED_MODULES} | {"revision.rego"}
    expected = {}
    for row in rows:
        name, sha = row["path"], row["sha256"]
        if name == "template.json":
            continue
        if name not in expected_names or name in expected or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("policy_observation_manifest_unsupported")
        expected[name] = sha
    if set(expected) != expected_names:
        raise ValueError("policy_observation_manifest_unsupported")
    observed = {}
    for module in modules:
        identifier, raw = module["id"], module["raw"]
        if not isinstance(identifier, str) or identifier in observed or not isinstance(raw, str):
            raise ValueError("policy_observation_invalid")
        observed[identifier] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return Counter(observed.values()) == Counter(expected.values())


def compare_loaded_data(manifest, template, root):
    """Compare every registered base-document root, including stage manifest.

    OPA's root Data API also returns virtual documents under pocketlab. These
    cannot be distinguished from arbitrary injected base data solely by that
    API; do not claim an in-memory attestation. Stage-file proof is separate.
    """
    if not isinstance(root, dict) or not isinstance(manifest, dict):
        return False
    expected = {**template, **manifest}
    if set(root) != set(expected) | {"pocketlab"}:
        return False
    if not isinstance(root["pocketlab"], dict):
        return False
    return all(canonical_bytes(root.get(key)) == canonical_bytes(value) for key, value in expected.items())


def _snapshot():
    from ..db.connection import read_connection
    from . import lite_policy_lifecycle as lifecycle
    with read_connection() as conn:
        row = conn.execute("""SELECT s.active_revision_id,s.known_good_revision_id,r.content_hash,r.manifest_json,
                r.template_id,r.template_version,r.canonical_parameters_json
            FROM policy_runtime_state s JOIN policy_revisions r ON s.active_revision_id=r.revision_id
            WHERE s.state_id=1""").fetchone()
        pending = conn.execute("""SELECT 1 FROM policy_activation_operations
            WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain')
            LIMIT 1""").fetchone()
    if not row or pending or row["active_revision_id"] != row["known_good_revision_id"]:
        return None
    revision = row["active_revision_id"]
    if lifecycle._pointer_revision("active") != revision or lifecycle._pointer_revision("known-good") != revision:
        return None
    return (revision, row["content_hash"], row["manifest_json"], row["template_id"],
            row["template_version"], row["canonical_parameters_json"])


def observe():
    result = {"state": "unknown", "scope": "rego_modules_only",
              "data_identity": "unknown", "manifest_data_identity": "unknown", "backend_identity": "unknown",
              "execution_eligible": False, "module_identity_sha256": "", "data_identity_sha256": ""}
    try:
        snapshot = _snapshot()
        if snapshot is None:
            return result
        revision, content_hash, manifest_json, template_id, template_version, parameters_json = snapshot
        if _get("/v1/data/pocketlab/meta/revision") != revision:
            return {**result, "state": "revision_mismatch"}
        modules = _get("/v1/policies")
        manifest = json.loads(manifest_json)
        if isinstance(manifest, list):
            manifest = {"files": manifest}
        if hashlib.sha256(canonical_bytes(manifest["files"])).hexdigest() != content_hash:
            return result
        matched = compare_loaded_modules(manifest, modules)
        expected_data = {"template_id": template_id, "template_version": template_version,
                         "parameters": json.loads(parameters_json)}
        # Probe only the registered generated data documents. Do not evaluate
        # the entire virtual policy tree, which can depend on input or time.
        data_matches = all(canonical_bytes(_get("/v1/data/" + key)) == canonical_bytes(value)
                           for key, value in expected_data.items())
        expected_manifest = {"revision": revision, "files": manifest["files"], "candidate_hash": content_hash}
        manifest_matches = compare_loaded_data(expected_manifest, expected_data, _get("/v1/data"))
        module_rows = [
            {
                "id": item.get("id"),
                "raw_sha256": hashlib.sha256(str(item.get("raw") or "").encode("utf-8")).hexdigest(),
            }
            for item in modules
            if isinstance(item, dict)
        ]
        module_identity = hashlib.sha256(canonical_bytes(sorted(
            module_rows,
            key=lambda item: (str(item.get("id") or ""), str(item.get("raw_sha256") or "")),
        ))).hexdigest()
        data_identity = hashlib.sha256(canonical_bytes({
            "manifest": expected_manifest,
            "expected_data": expected_data,
            "observed_root": _get("/v1/data"),
        })).hexdigest()
        if _get("/v1/data/pocketlab/meta/revision") != revision or _snapshot() != snapshot:
            return result
        return {**result, "state": "modules_match" if matched else "module_mismatch",
                "observed_revision": revision, "observed_at": datetime.now(timezone.utc).isoformat(),
                "data_identity": "registered_template_matches" if data_matches else "registered_template_mismatch",
                "manifest_data_identity": "registered_roots_match" if manifest_matches else "registered_roots_mismatch",
                "module_identity_sha256": module_identity,
                "data_identity_sha256": data_identity}
    except Exception:
        return result
