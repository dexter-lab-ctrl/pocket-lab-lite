"""Dependency-free shared release packaging profile (publisher and verifier)."""

POLICY_PREFIX = "security/policies/opa/"
MIGRATION_PREFIX = "pocket-lab-final-structure/runtime/api_fastapi/db/schema/"
RUNTIME = "pocket-lab-final-structure/runtime/"
BOOTSTRAP = "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/"
RUNTIME_PROFILE = "runtime-review-v1"
# This is a review/staging package, not an installable runtime image.
# Keep dependencies used by the native owner, contracts and policy inventory;
# omit the frontend source, docs, test suites and unrelated repository trees.
RUNTIME_PROFILE_ROOTS = (
    RUNTIME.rstrip("/"), BOOTSTRAP.rstrip("/"), POLICY_PREFIX.rstrip("/"),
    "scripts/dev/lite", "contracts", "schemas", "operations", "runbooks",
    "package.json", "package-lock.json",
)
