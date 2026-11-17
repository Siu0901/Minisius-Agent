---
name: complete-milestone
description: 마일스톤을 닫기 전에 완료 조건과 검증 결과를 실제로 대조한다. "v0.1-alpha 마무리하자", "마일스톤 완료 확인" 같은 요청에 쓴다.
argument-hint: "[마일스톤, 예: v0.1-alpha]"
---

# 마일스톤 종료

대상: `$ARGUMENTS` (비어 있으면 `.harness/progress.md` 의 Current Milestone)

상태 파일을 믿지 않고 실제와 대조한다.

## 1. 기능 대조

`.harness/features.json` 에서 대상 마일스톤의 기능마다:
- `passes: true` 인가.
- `tests` 에 적힌 테스트가 실제로 있고, 그 테스트가 `docs/PRD.md` 의 완료 조건을 다루는가. 이름만 있는 빈 테스트가 아닌가.

하나라도 아니면 마일스톤은 닫지 않는다. 해당 기능을 `passes: false` 로 되돌리고 목록으로 보고한다.

## 2. 전체 검증

```bash
./scripts/verify.sh
```

## 3. 완료 목표 실행

`docs/ROADMAP.md` 의 "완료 목표"를 실제로 실행해 본다(예: v0.1-alpha 면 CLI 로 파일을 읽고 답하게 한다).
실제 API 키가 필요해 실행할 수 없으면 사용자에게 실행을 부탁하고, 확인하지 못했다고 적는다.

## 4. 리뷰

`architecture-reviewer` 와 `test-reviewer` 에이전트에게 마일스톤 전체를 검토시킨다.
지적을 반영했으면 2번을 다시 돌린다.

## 5. 문서 정리

- `docs/PRD.md`, `docs/ARCHITECTURE.md`: 구현하면서 달라진 부분과 채워진 "미정"을 반영한다.
- `docs/DECISIONS.md`: 마일스톤 중 내린 결정이 빠지지 않았는지 본다.
- `.harness/features.json`: 다음 마일스톤의 `-F00` 항목을 세부 기능으로 쪼갠다. 사용자와 상의한다.
- `.harness/progress.md`: Current Milestone 을 다음으로 바꾼다.

## 6. 보고

통과한 것, 확인하지 못한 것, 다음 마일스톤의 첫 작업을 말한다. 커밋과 태그는 사용자가 요청하면 한다.
