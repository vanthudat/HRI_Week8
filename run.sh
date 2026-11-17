#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PYTHONNOUSERSITE=1
if [[ ! -x .venv-emotion/bin/python ]]; then
    echo "Chưa có venv. Chạy bash install.sh trước." >&2
    exit 1
fi
if [[ "${1:-}" == "--check" ]]; then
    exec .venv-emotion/bin/python -s check_environment.py
fi
exec .venv-emotion/bin/python -s -m facial_expression_control "$@"
