"""Dependency-free shared release packaging profile (publisher and verifier)."""

POLICY_PREFIX = "security/policies/opa/"
MIGRATION_PREFIX = "pocket-lab-final-structure/runtime/api_fastapi/db/schema/"
RUNTIME = "pocket-lab-final-structure/runtime/"
BOOTSTRAP = "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/"
RUNTIME_PROFILE = "runtime-review-v1"
INSTALLABLE_RUNTIME_PROFILE = "runtime-install-v1"
DEPENDENCY_MANIFEST = RUNTIME + "runtime-dependencies.json"
# The review profile remains supported for existing signed declarations.  It
# is intentionally not execution-eligible.  The install profile adds the
# explicit dependency closure and is the only profile admitted to a live
# isolated runtime owner.
RUNTIME_PROFILE_ROOTS = (
    RUNTIME.rstrip("/"), BOOTSTRAP.rstrip("/"), POLICY_PREFIX.rstrip("/"),
    "scripts/dev/lite", "contracts", "schemas", "operations", "runbooks",
    "package.json", "package-lock.json",
)
