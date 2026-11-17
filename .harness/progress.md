# Development Progress

다음 세션에 넘기는 인수인계 기록. 세션을 끝낼 때 `/handoff` 로 갱신한다.
지난 일의 기록이 아니라 **다음 세션이 알아야 할 것**만 남긴다. 오래된 내용은 지운다.

마지막 갱신: 2026-11-18

## Current Milestone

v0.1-alpha (3/11 완료)

## Completed

- M0-F01 개발 하네스
- V01A-F01 예외 계층 (`src/minisius/errors.py`). 아키텍처 검사기에 A7(예외 클래스는 errors.py 에만) 추가
- V01A-F02 내부 표준 메시지 포맷 (`src/minisius/core/messages.py`)
- V01A-F03 설정과 경로 규칙 (`src/minisius/config.py`). 브랜치 `feat/v01a-f03-config`

## Current Work

V01A-F03 은 구현과 검증이 끝났고 브랜치 `feat/v01a-f03-config` 에서 사용자의 점검을 기다린다.
사용자가 커밋·푸시한 뒤 `main` 대상 PR 을 만든다.

## Test Results

- `./scripts/verify.sh`: PASS (2026-11-18, 테스트 82개)

## Known Issues

- 없음. 남은 미정 항목은 `docs/ARCHITECTURE.md` 9절과 `docs/PRD.md` 의 완료 조건에 있다.

## Next Task

`/implement-feature V01A-F04`(이벤트 타입과 append-only 이벤트 로그, `core/events.py`, `store/`). 새 브랜치에서 시작한다.
SQLite 스키마와 이벤트 타입별 payload 필드는 아직 정해지지 않았다. 구현 전에 사용자와 정한다(`docs/ARCHITECTURE.md` 5.6절, 9절).

v0.1 은 alpha 와 beta 로 나뉜다(ADR-019). alpha 는 Anthropic 어댑터와 읽기 전용 도구만으로
Agent Loop 를 실제로 돌리는 데까지다. 쓰기·셸 도구는 권한 정책과 함께 beta 에 들어온다(ADR-018).

alpha 중에 하네스 검증 실험을 한 번 한다: 기능을 일부러 중간에 멈추고 새 세션에서 이어받는지,
`features.json` 을 일부러 실제와 다르게 만들었을 때 세션 시작 절차가 잡아내는지 확인한다.
