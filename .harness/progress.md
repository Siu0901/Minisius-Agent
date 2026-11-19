# Development Progress

다음 세션에 넘기는 인수인계 기록. 세션을 끝낼 때 `/handoff` 로 갱신한다.
지난 일의 기록이 아니라 **다음 세션이 알아야 할 것**만 남긴다. 오래된 내용은 지운다.

마지막 갱신: 2026-11-18

## Current Milestone

v0.1-alpha (4/11 완료)

## Completed

- M0-F01 개발 하네스
- V01A-F01 예외 계층 (`src/minisius/errors.py`). 아키텍처 검사기에 A7(예외 클래스는 errors.py 에만) 추가
- V01A-F02 내부 표준 메시지 포맷 (`src/minisius/core/messages.py`)
- V01A-F03 설정과 경로 규칙 (`src/minisius/config.py`)
- V01A-F04 이벤트 타입과 이벤트 로그 (`core/actions.py`, `core/events.py`, `store/db.py`, `store/event_log.py`). 브랜치 `feat/v01a-f04-event-log`

## Current Work

V01A-F04 는 구현과 검증이 끝났고 브랜치 `feat/v01a-f04-event-log` 에서 사용자의 점검을 기다린다.
사용자가 커밋·푸시한 뒤 `main` 대상 PR 을 만든다.

## Test Results

- `./scripts/verify.sh`: PASS (2026-11-18, 테스트 127개)

## Known Issues

- 이벤트 로그는 도구 인수와 결과를 걸러내지 않고 기록한다. 비밀 값 처리는 미정(`docs/ARCHITECTURE.md` 9절).

## Next Task

`/implement-feature V01A-F05`(Provider 인터페이스와 모델 메타데이터, `providers/base.py`, `providers/models.py`). 새 브랜치에서 시작한다.

F05 에서 같이 볼 것:
- `core/events.py` 의 `LLMResponded.stop_reason` 은 지금 문자열 Literal 이다. `providers.base.StopReason` 이 생기면 그것으로 바꾼다.
- `core/events.py` 의 `Usage`(세션 합계)와 `providers/base.py` 의 `Usage`(응답 하나)는 이름이 같다. 헷갈리면 한쪽 이름을 바꾼다.

F10(Agent Loop) 에서 지킬 것: LLM 에 돌려준 도구 결과는 인수 검증 실패까지 모두 `tool_call_finished` 로 남긴다.
대화를 이벤트에서만 만들어 내기 때문이다(`docs/ARCHITECTURE.md` 5.6절).

v0.1 은 alpha 와 beta 로 나뉜다(ADR-019). alpha 는 Anthropic 어댑터와 읽기 전용 도구만으로
Agent Loop 를 실제로 돌리는 데까지다. 쓰기·셸 도구는 권한 정책과 함께 beta 에 들어온다(ADR-018).

alpha 중에 하네스 검증 실험을 한 번 한다: 기능을 일부러 중간에 멈추고 새 세션에서 이어받는지,
`features.json` 을 일부러 실제와 다르게 만들었을 때 세션 시작 절차가 잡아내는지 확인한다.
