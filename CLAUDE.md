# Minisius Agent

CLI와 Discord로 말을 거는 설치형 범용 AI 에이전트(미니 Hermes). 에이전트 프레임워크 없이
런타임을 Python으로 직접 구현한다. 가장 중요한 결과물은 그럴듯한 답변이 아니라, 작업을
계획·실행·검증하고 실패했을 때 안전하게 복구하는 시스템이다.

## 필수 원칙

- LangChain, LangGraph 같은 에이전트 프레임워크를 쓰지 않는다.
- 런타임(`core`)과 LLM 프로바이더를 분리한다. SDK는 어댑터 파일에서만 import 한다.
- 모든 실행 과정은 append-only 이벤트 로그에 남긴다.
- 도구는 `execution` 백엔드를 거치고, 권한 판정은 `policy` 가 한다.
- uv 를 쓴다. Python 3.12+.
- 모든 기능에 테스트를 쓴다. `./scripts/verify.sh` 가 통과해야 완료다.
- 정해지지 않은 것("미정")은 추측으로 구현하지 않고 사용자와 먼저 정한다.

## 세션 시작

1. `.harness/session-protocol.md` 의 절차를 따른다.
2. `.harness/progress.md` 로 이전 세션의 상태를 확인한다.
3. `.harness/features.json` 으로 다음 기능을 확인한다.
4. `./scripts/verify.sh` 를 직접 돌려 상태 파일과 실제가 맞는지 확인한다.
5. 기능 하나를 `/implement-feature` 로 구현하고, 끝낼 때 `/handoff` 한다.

## 문서 위치

| 알고 싶은 것 | 파일 |
|---|---|
| 무엇을 만드는가, 완료 조건 | `docs/PRD.md` |
| 구조, 의존 규칙, 오류 처리 | `docs/ARCHITECTURE.md` |
| 마일스톤 순서 | `docs/ROADMAP.md` |
| 왜 이렇게 정했는가 | `docs/DECISIONS.md` |
| 어떻게 검증하는가 | `docs/TESTING.md` |
| 기능별 상태 | `.harness/features.json` |
| 지금 하던 일, 다음 할 일 | `.harness/progress.md` |

같은 내용을 두 곳에 적지 않는다. 문서를 고칠 때는 원본 하나만 고친다.

## 명령

```bash
./scripts/init.sh      # 의존성 설치
./scripts/verify.sh    # ruff, mypy, pytest, 아키텍처 검사, features.json 검사
```

## 스킬과 에이전트

- `/implement-feature [기능 ID]`: 기능 하나를 확인·구현·검증·상태 갱신까지
- `/trace-agent-loop [시나리오]`: 실제 코드의 호출 흐름 추적
- `/complete-milestone [마일스톤]`: 마일스톤 종료 전 대조
- `/handoff`: 세션 종료 전 인수인계
- `architecture-reviewer`, `test-reviewer`: 읽기 전용 검토 에이전트
