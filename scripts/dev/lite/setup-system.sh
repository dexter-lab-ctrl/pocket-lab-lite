#!/usr/bin/env bash
set -euo pipefail
cat <<'MSG'
Pocket Lab Lite does not require sqlite3 CLI or Graphviz for the implemented documentation platform.
Python's built-in sqlite3 module and Mermaid source are used instead.
No system package will be installed and sudo will not be invoked.
MSG
