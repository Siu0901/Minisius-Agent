# Session Protocol

세션을 시작하고 끝내는 절차. 기억이 아니라 파일, git, 테스트 결과로 현재 상태를 확인한다.

## 세션 시작

1. `git status` 와 최근 커밋을 본다. 커밋되지 않은 변경이 있으면 이전 세션이 중간에 끊긴 것이다.
2. `.harness/progress.md` 를 읽는다. Current Work, Known Issues, Next Task 를 확인한다.
3. `.harness/features.json` 에서 `in_progress` 와 다음 `pending` 기능을 확인한다.
4. `./scripts/verify.sh` 를 실행한다. 상태 파일이 PASS 라고 해도 직접 돌려서 확인한다.
   실패하면 새 기능보다 먼저 고친다.
5. 상태 파일과 실제가 다르면(예: `passes: true` 인데 테스트가 없거나 실패) 상태 파일을 실제에 맞게 고치고 사용자에게 알린다.

## 작업

- 한 번에 기능 하나. `features.json` 에서 `in_progress` 는 하나만 둔다.
- 기능 구현은 `/implement-feature <기능 ID>` 절차를 따른다.
- 사용자가 따로 지시하지 않으면 `features.json` 의 순서대로 진행한다.
- 완료 조건이 "미정"인 기능은 구현하기 전에 사용자와 정하고 `docs/PRD.md` 에 적는다.
- 설계 결정을 새로 내리거나 바꾸면 `docs/DECISIONS.md` 에 추가한다.

## 완료 판정

기능을 `completed` / `passes: true` 로 바꾸는 조건은 전부 충족해야 한다.

1. `docs/PRD.md` 의 완료 조건마다 대응하는 테스트가 있다.
2. `features.json` 의 `tests` 에 그 테스트 경로를 적었다.
3. `./scripts/verify.sh` 가 통과했다.

코드를 다 썼지만 검증이 안 됐으면 `in_progress` / `passes: false` 로 둔다.

## 세션 종료

1. `./scripts/verify.sh` 를 실행하고 결과를 기록한다.
2. `.harness/features.json` 을 갱신한다.
3. `.harness/progress.md` 를 갱신한다(`/handoff`). 끝내지 못한 작업, 실패 원인, 다음에 할 일을 적는다.
4. 커밋은 사용자가 요청할 때만 한다.

## 정보의 원본

같은 내용을 두 곳에 적지 않는다. 필요하면 링크한다.

| 정보 | 원본 |
|---|---|
| 제품 요구사항, 완료 조건 | `docs/PRD.md` |
| 구조, 의존 규칙 | `docs/ARCHITECTURE.md` |
| 마일스톤 순서 | `docs/ROADMAP.md` |
| 결정과 이유 | `docs/DECISIONS.md` |
| 검증 방법 | `docs/TESTING.md` |
| 기능별 검증 상태 | `.harness/features.json` |
| 현재 작업과 인수인계 | `.harness/progress.md` |
| 기능 개발 절차 | `.claude/skills/implement-feature/SKILL.md` |
