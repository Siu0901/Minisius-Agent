---
name: implement-feature
description: features.json 의 기능 하나를 요구사항 확인부터 검증까지 구현한다. "다음 기능 구현해줘", "V01A-F02 구현" 같은 요청에 쓴다.
argument-hint: "[기능 ID, 예: V01A-F02]"
---

# 기능 구현

대상: `$ARGUMENTS` (비어 있으면 `.harness/features.json` 의 `in_progress`, 없으면 첫 `pending`)

## 1. 확인

- `.harness/features.json` 에서 대상 기능의 `spec` 을 보고 `docs/PRD.md` 의 완료 조건을 읽는다.
- `docs/ARCHITECTURE.md` 에서 이 기능이 들어갈 파일과 의존 규칙을 확인한다.
- 완료 조건이나 인터페이스가 "미정"이면 구현하지 않는다. 안을 제시해 사용자와 정하고, 정한 내용을 문서에 먼저 적는다.
- 이 기능이 앞선 기능에 의존하는데 그 기능이 `passes: false` 면 사용자에게 알린다.

## 2. 시작 표시

`main` 에서 브랜치를 판다: `git switch -c feat/<기능 ID 소문자>-<짧은 이름>`. 이미 그 기능의 브랜치에 있으면 그대로 쓴다.

`features.json` 에서 대상의 `status` 를 `in_progress` 로 바꾼다. 다른 `in_progress` 가 있으면 먼저 그것을 끝내거나 사용자에게 묻는다.

## 3. 구현

- 완료 조건 하나마다 테스트를 쓴다. 오류 경로를 포함한다.
- `.claude/rules/` 의 규칙을 따른다.
- 범위를 넘지 않는다. 다음 기능에 속하는 것은 만들지 않는다.

## 4. 검증

```bash
./scripts/verify.sh
```

실패하면 고치고 다시 돌린다. 통과할 때까지 완료가 아니다.

구조에 영향이 큰 기능(core, providers, tools, execution, policy)은 `architecture-reviewer` 에이전트에게 검토를 맡기고, 지적을 반영한 뒤 다시 검증한다.

## 5. 상태 갱신

검증이 통과하면:
- `features.json`: `status: completed`, `passes: true`, `tests` 에 테스트 경로.
- `.harness/progress.md`: Completed, Test Results, Next Task.
- 새 설계 결정이 있었으면 `docs/DECISIONS.md`.

통과하지 못한 채 세션이 끝나면 `in_progress` / `passes: false` 로 두고 `/handoff` 한다.

## 6. 보고

무엇을 만들었는지, verify.sh 결과, 완료 조건 중 검증하지 못한 것이 있으면 그것을 말한다.

커밋과 푸시는 하지 않는다. 사용자가 점검한 뒤 직접 한다. 사용자가 푸시했다고 알리면 `main` 대상 PR 을 만든다.
