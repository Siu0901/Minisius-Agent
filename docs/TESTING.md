# TESTING — Minisius Agent

어떻게 검증하는지의 원본. 실제 테스트는 `tests/` 에 있고 `./scripts/verify.sh` 가 실행한다.
여기에 적힌 것과 실제 테스트 코드가 있는 것은 다르다. 완료 판정은 항상 실행 결과로 한다.

## 검증 명령

```bash
./scripts/verify.sh
```

순서대로 ruff check, ruff format --check, mypy(strict), pytest, check_architecture, check_features 를
끝까지 실행하고 실패 목록을 보여준다. 하나라도 실패하면 종료 코드 1.

## 테스트 계층

| 계층 | 대상 | 방법 |
|---|---|---|
| Unit | 메시지 변환, Tool Registry, 정책 판정, 이벤트 로그 | 외부 의존 없이 |
| Integration | Agent Loop | 대본대로 응답하는 가짜 Provider 로 API 비용 없이 |
| E2E | CLI 로 실제 작업 | 임시 작업 폴더에서 |
| Security | 작업 폴더 밖 수정, 민감 경로 읽기, 위험 명령 | 차단·승인 요청이 나오는지 |
| Harness | `scripts/` 의 검사기 | `tests/harness/` |

## 원칙

- 새 기능에는 테스트를 같이 쓴다. `features.json` 의 `tests` 에 그 경로를 적는다.
- 정상 경로뿐 아니라 오류 경로를 검증한다(잘못된 인수, 타임아웃, 재시도, 반복 실패 차단).
- 기본 테스트는 네트워크와 실제 API 키 없이 돈다. 실제 프로바이더를 부르는 테스트는 별도 마커로 분리한다.
- 파일을 건드리는 테스트는 `tmp_path` 안에서만 한다. 실제 `~/.minisius/` 를 쓰지 않는다.

## 미정

- 가짜 Provider 의 형태(대본 형식)
- 실제 프로바이더 테스트의 마커 이름과 실행 방법
- E2E 테스트의 범위
- v0.8 평가 과제의 형식과 채점 방식
