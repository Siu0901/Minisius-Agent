#!/usr/bin/env python3
""".harness/features.json 일관성 검사기.

features.json 은 사람이든 에이전트든 잘못 고칠 수 있으므로, 최소한의 모순은 코드로 막는다.

검사 항목:
- 형식: id 중복 없음, status 값, passes 타입, tests 목록
- passes 가 true 면 status 는 completed 이고, tests 에 적힌 파일이 실제로 있어야 한다
- status 가 completed 면 passes 가 true 여야 한다
- in_progress 는 동시에 하나만

테스트가 실제로 통과하는지는 여기서 보지 않는다. 그건 verify.sh 의 pytest 가 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_FILE = REPO / ".harness" / "features.json"
STATUSES = ("pending", "in_progress", "completed")


def check(data: object, repo: Path) -> list[str]:
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        return ["최상위에 'features' 배열이 있어야 한다"]

    errors: list[str] = []
    seen: set[str] = set()
    in_progress: list[str] = []

    for index, feature in enumerate(data["features"]):
        if not isinstance(feature, dict):
            errors.append(f"features[{index}]: 객체가 아니다")
            continue
        fid = feature.get("id")
        label = fid if isinstance(fid, str) and fid else f"features[{index}]"
        if not isinstance(fid, str) or not fid:
            errors.append(f"{label}: id 가 없다")
        elif fid in seen:
            errors.append(f"{label}: id 가 중복된다")
        else:
            seen.add(fid)

        for key in ("name", "milestone"):
            if not isinstance(feature.get(key), str) or not feature[key]:
                errors.append(f"{label}: {key} 가 없다")

        status = feature.get("status")
        passes = feature.get("passes")
        tests = feature.get("tests", [])
        if status not in STATUSES:
            errors.append(f"{label}: status 는 {', '.join(STATUSES)} 중 하나여야 한다")
        if not isinstance(passes, bool):
            errors.append(f"{label}: passes 는 true/false 여야 한다")
        if not isinstance(tests, list) or not all(isinstance(t, str) for t in tests):
            errors.append(f"{label}: tests 는 문자열 배열이어야 한다")
            tests = []

        if status == "in_progress":
            in_progress.append(label)
        if passes is True and status != "completed":
            errors.append(f"{label}: passes 가 true 인데 status 가 completed 가 아니다")
        if status == "completed" and passes is not True:
            errors.append(f"{label}: completed 인데 passes 가 true 가 아니다")
        if passes is True and not tests:
            errors.append(f"{label}: passes 가 true 인데 tests 가 비어 있다")
        if passes is True:
            errors.extend(
                f"{label}: tests 의 파일이 없다: {test}"
                for test in tests
                if not (repo / test.split("::")[0]).exists()
            )

    if len(in_progress) > 1:
        errors.append(f"in_progress 는 하나만 둔다: {', '.join(in_progress)}")
    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check_features: {path} 를 읽지 못했다: {exc}", file=sys.stderr)
        return 2
    errors = check(data, REPO)
    for error in errors:
        print(error)
    if errors:
        print(f"\nfeatures.json 문제 {len(errors)}건", file=sys.stderr)
        return 1
    print("check_features: 문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
