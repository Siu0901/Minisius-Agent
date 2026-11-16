---
name: handoff
description: 세션을 끝내기 전에 현재 상태, 문제, 다음 작업을 .harness/ 에 기록한다. "오늘은 여기까지", "인수인계 정리해줘" 같은 요청에 쓴다.
---

# 인수인계

다음 세션은 이 대화를 볼 수 없다. 파일만 보고 이어갈 수 있게 남긴다.

## 1. 실제 상태 확인

```bash
git status --short
./scripts/verify.sh
```

## 2. features.json 갱신

- 검증을 통과한 기능만 `completed` / `passes: true`.
- 작업 중인 기능은 `in_progress` / `passes: false`.
- `uv run python scripts/check_features.py` 로 형식을 확인한다.

## 3. progress.md 갱신

`.harness/progress.md` 를 덮어쓴다. 쌓지 않는다. 섹션은 그대로 유지한다.

- **마지막 갱신**: 오늘 날짜
- **Current Milestone**
- **Completed**: 이번 마일스톤에서 끝난 기능 ID 와 이름
- **Current Work**: 하던 일. 어디까지 했고 어디서 멈췄는지를 파일과 함수 이름으로
- **Test Results**: verify.sh 결과. 실패가 있으면 어떤 검사, 어떤 테스트인지
- **Known Issues**: 실패 원인으로 추정하는 것, 시도했는데 안 된 방법, 정해지지 않은 결정
- **Next Task**: 다음 세션이 처음 할 일 하나를 구체적으로

적지 않는 것: 코드나 git 기록으로 알 수 있는 것, 이번 세션의 경과.

## 4. 보고

갱신한 내용을 서너 줄로 말한다. 커밋되지 않은 변경이 있으면 알린다. 커밋은 사용자가 요청하면 한다.
