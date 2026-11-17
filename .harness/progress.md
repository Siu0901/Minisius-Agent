# Development Progress

다음 세션에 넘기는 인수인계 기록. 세션을 끝낼 때 `/handoff` 로 갱신한다.
지난 일의 기록이 아니라 **다음 세션이 알아야 할 것**만 남긴다. 오래된 내용은 지운다.

마지막 갱신: 2026-11-17

## Current Milestone

v0.1-alpha (1/11 완료)

## Completed

- M0-F01 개발 하네스
- V01A-F01 예외 계층 (`src/minisius/errors.py`). 아키텍처 검사기에 A7(예외 클래스는 errors.py 에만) 추가

## Current Work

없음.

## Test Results

- `./scripts/verify.sh`: PASS (2026-11-17, 테스트 22개)

## Known Issues

- 없음. 남은 미정 항목은 `docs/ARCHITECTURE.md` 9절과 `docs/PRD.md` 의 완료 조건에 있다.

## Next Task

`/implement-feature V01A-F02`(내부 표준 메시지 포맷, `core/messages.py`). 타입은 `docs/ARCHITECTURE.md` 5.1절에 확정돼 있다.

v0.1 은 alpha 와 beta 로 나뉜다(ADR-019). alpha 는 Anthropic 어댑터와 읽기 전용 도구만으로
Agent Loop 를 실제로 돌리는 데까지다. 쓰기·셸 도구는 권한 정책과 함께 beta 에 들어온다(ADR-018).

alpha 중에 하네스 검증 실험을 한 번 한다: 기능을 일부러 중간에 멈추고 새 세션에서 이어받는지,
`features.json` 을 일부러 실제와 다르게 만들었을 때 세션 시작 절차가 잡아내는지 확인한다.
