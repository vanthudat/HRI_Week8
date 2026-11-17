#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PYTHONNOUSERSITE=1
export PIP_DEFAULT_TIMEOUT=30
export PIP_RETRIES=2
if [[ ! -x .venv-emotion/bin/python ]]; then
    /usr/bin/python3 -m venv --system-site-packages .venv-emotion
fi
# Cài gói nhỏ trước; lỗi tải SciPy không ngăn cài tf-keras để sửa lỗi import.
.venv-emotion/bin/python -s -m pip install tf-keras==2.15.1
.venv-emotion/bin/python -s -m pip install --upgrade --upgrade-strategy only-if-needed -r requirements.txt
.venv-emotion/bin/python -s check_environment.py
