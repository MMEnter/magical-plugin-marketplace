#!/bin/sh
# Generates this case's synthetic fixture in the sandbox working folder.
set -e
PY="$(command -v python3 || command -v python)"
"$PY" "$(dirname "$0")/../../tests/make_fixtures.py" critical-marketplace "$PWD" >/dev/null
