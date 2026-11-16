---
paths:
  - "src/**"
---

# 아키텍처 규칙

원본은 `docs/ARCHITECTURE.md` 3절이다. 여기는 코드를 쓸 때 바로 떠올려야 할 요약이다.

- 에이전트 프레임워크를 쓰지 않는다.
- 프로바이더 SDK는 각자의 어댑터 파일에서만 import 한다.
- `core` 는 `providers.base` 와 `providers.models` 만 안다. `interfaces` 를 모른다.
- 도구는 파일과 프로세스에 직접 손대지 않고 `execution` 백엔드를 거친다.
- 도구는 권한을 판정하지 않는다. Agent Loop 가 실행 전에 `policy` 에 묻는다.
- 도구는 예외를 잡지 않고 `ToolError` 로 던진다. 도구 결과로 바꾸는 건 Registry 가 한다.
- 새 예외는 `errors.py` 에 추가한다. 다른 곳에 예외 클래스를 만들지 않는다.
- 런타임에서 일어나는 일은 이벤트 로그에 남긴다. 로그를 거치지 않는 상태를 따로 두지 않는다.

규칙을 지켰는지는 `uv run python scripts/check_architecture.py` 로 확인한다.
규칙이 작업을 막으면 우회하지 말고 사용자와 상의해 `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
검사기를 함께 고친다.
