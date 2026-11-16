# Development Progress

다음 세션에 넘기는 인수인계 기록. 세션을 끝낼 때 `/handoff` 로 갱신한다.
지난 일의 기록이 아니라 **다음 세션이 알아야 할 것**만 남긴다. 오래된 내용은 지운다.

마지막 갱신: 2026-11-17

## Current Milestone

M0 완료. 다음은 v0.1.

## Completed

- M0-F01 개발 하네스: 문서 5개, 상태 파일, 검증 스크립트, Claude Code 규칙·스킬·에이전트

## Current Work

없음.

## Test Results

- `./scripts/verify.sh`: PASS (2026-11-17)

## Known Issues

- 핵심 인터페이스(Message, Event, Tool, Provider, ExecutionBackend, Frontend)의 타입 정의가 아직 없다. `docs/ARCHITECTURE.md` 5절이 미정이다.

## Next Task

v0.1 을 시작하기 전에 핵심 인터페이스의 타입을 설계해 `docs/ARCHITECTURE.md` 5절을 채운다.
그 다음 V01-F01(예외 계층)부터 `features.json` 순서대로 구현한다.
