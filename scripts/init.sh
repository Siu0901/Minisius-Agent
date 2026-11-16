#!/usr/bin/env bash
# 저장소를 처음 받았을 때, 또는 의존성이 바뀌었을 때 실행한다.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv 가 없다. https://docs.astral.sh/uv/ 를 보고 설치한 뒤 다시 실행한다." >&2
    exit 1
fi

uv sync
uv run python --version
uv run pytest --version
uv run ruff --version
uv run mypy --version

echo
echo "준비 완료. 검증은 ./scripts/verify.sh"
