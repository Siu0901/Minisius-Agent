#!/usr/bin/env bash
# 코드 변경 후 실행하는 전체 검증. 하나라도 실패하면 종료 코드 1.
# 첫 실패에서 멈추지 않고 끝까지 돌려서 실패 목록을 한 번에 보여준다.
set -uo pipefail

cd "$(dirname "$0")/.."

failed=()

run() {
    local name="$1"
    shift
    echo
    echo "== ${name}"
    if "$@"; then
        echo "-- ${name}: PASS"
    else
        echo "-- ${name}: FAIL"
        failed+=("${name}")
    fi
}

run "ruff check"         uv run ruff check .
run "ruff format"        uv run ruff format --check .
run "mypy"               uv run mypy
run "pytest"             uv run pytest
run "check_architecture" uv run python scripts/check_architecture.py
run "check_features"     uv run python scripts/check_features.py

echo
if [ "${#failed[@]}" -gt 0 ]; then
    echo "VERIFY FAILED: ${failed[*]}"
    exit 1
fi
echo "VERIFY OK"
