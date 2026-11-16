# ARCHITECTURE — Minisius Agent

어떻게 만드는지의 원본. 결정의 이유는 [DECISIONS.md](DECISIONS.md).

## 1. 뼈대: append-only 이벤트 로그

모든 일(LLM 요청·응답, 도구 호출 의도, 도구 결과, 승인, 계획 변경, 오류)을 SQLite 이벤트 로그에
순서대로 쌓는다. 나머지 기능은 이 로그를 읽는 방식이다.

| 기능 | 이벤트 로그와의 관계 |
|---|---|
| 세션 재개·복구 | 로그를 다시 읽어 상태를 재구성한다. 의도는 있는데 결과가 없는 도구 호출이 중단 지점이다 |
| Context Compaction | 로그는 그대로 두고 LLM에 보낼 뷰만 압축한다 |
| 추적 | 로그가 곧 트레이스다. 토큰·비용은 집계 쿼리다 |
| 평가 | 실행 한 번이 로그 한 개다. 사후에 채점한다 |
| CLI·Discord | 이벤트 스트림을 구독하는 어댑터다 |

## 2. 디렉터리 구조

```
src/minisius/
├── __main__.py
├── config.py              # Pydantic 설정, 경로 규칙
├── errors.py              # 예외 계층 전체
├── core/                  # 런타임
│   ├── messages.py        # 내부 표준 메시지 포맷
│   ├── events.py          # 이벤트 타입
│   ├── loop.py            # Agent Loop
│   ├── session.py         # 세션 조립·수명·재개
│   ├── context.py         # 프롬프트 조립, Compaction (v0.3)
│   └── planner.py         # 계획 (v0.6)
├── providers/
│   ├── base.py            # Provider 인터페이스
│   ├── anthropic_adapter.py
│   ├── gemini_adapter.py
│   ├── openai_compat_adapter.py   # openrouter, ollama 공용
│   └── models.py          # 모델 메타데이터 표
├── tools/
│   ├── base.py            # Tool 인터페이스
│   ├── registry.py        # 등록, 실행 래퍼, 오류 변환
│   ├── files.py  shell.py  web.py
│   └── memory.py (v0.4)  skills.py (v0.5)  schedule.py (v0.6)
├── execution/
│   ├── base.py            # ExecutionBackend 인터페이스
│   ├── local.py
│   └── docker.py          # v0.7
├── policy/                # v0.2
│   ├── engine.py          # 허용·승인 필요·차단 판정
│   └── rules.py           # 경로 범위, 민감 경로, 명령 분류
├── store/
│   ├── db.py              # 스키마, 마이그레이션 (WAL 모드)
│   ├── event_log.py
│   └── search.py          # 세션 FTS (v0.4)
├── memory/                # v0.4
├── skills/                # v0.5, builtin/ 에 기본 SKILL.md
├── scheduler/             # v0.6
├── mcp_client/            # v0.7
├── interfaces/
│   ├── base.py            # Frontend 인터페이스
│   ├── cli/
│   └── discord/           # v0.2
├── service/               # systemd, launchd 등록 (v0.2)
└── evals/                 # v0.8
```

이름 주의: SDK 패키지와 겹치지 않도록 `anthropic_adapter.py`, `mcp_client/`, `execution/` 으로 짓는다.

## 3. 의존 규칙

아래 표는 `scripts/check_architecture.py` 의 `RULES` 와 일대일로 대응한다. 한쪽을 고치면 다른 쪽도 고친다.

| ID | 규칙 |
|---|---|
| A1 | 에이전트 프레임워크(LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen 등)를 import 하지 않는다 |
| A2 | 프로바이더 SDK(`anthropic`, `google.genai`, `openai`)는 각자의 어댑터 파일에서만 import 한다 |
| A3 | `interfaces` 는 최상위 계층이다. `interfaces` 와 `__main__` 외에는 `interfaces` 를 import 하지 않는다 |
| A4 | `core` 는 `providers.base` 와 `providers.models` 만 import 한다. 특정 어댑터를 모른다 |
| A5 | `tools` 는 프로세스를 직접 띄우지 않는다(`subprocess` 등 금지). `execution` 백엔드를 거친다 |
| A6 | `tools` 는 `policy` 를 import 하지 않는다. 권한 판정은 Agent Loop 가 도구 실행 전에 `policy` 에 묻는다 |

코드로 검사하지 못하는 규칙(리뷰로 확인):
- 도구는 파일을 내장 `open()` 으로 직접 열지 않고 `execution` 백엔드를 거친다.
- 런타임과 이벤트 로그는 내부 표준 메시지 포맷만 쓴다. 프로바이더 포맷이 `core` 로 새지 않는다.

## 4. LLM Provider

- 프로바이더 4개(`anthropic`, `gemini`, `openrouter`, `ollama`), 어댑터 3개.
  OpenRouter와 Ollama는 `OpenAICompatibleAdapter` 를 같이 쓰고 `base_url` 기본값과 API 키 필수 여부만 다르다.
- 내부 표준 메시지 포맷을 직접 정의하고 어댑터가 양방향으로 변환한다.
- 프로바이더 원본(thinking 블록, thought signature 등)은 불투명 필드에 보존해 그대로 되돌려 보낸다.
- 모델 메타데이터 표에 컨텍스트 크기, 토큰 단가, 도구 호출 지원 여부를 둔다.
- 도구 호출을 못 하는 모델은 시작할 때 오류로 거절한다. 텍스트 파싱 우회로는 만들지 않는다.

## 5. 핵심 인터페이스

Message, Event, Tool, Provider, ExecutionBackend, Frontend 의 타입 정의: **미정** (v0.1 첫 작업)

## 6. 오류 처리

예외 계층은 `errors.py` 한 파일에 둔다.

```
MinisiusError
├── ToolError
│   ├── ToolArgumentError
│   ├── ToolTimeoutError
│   └── PermissionDenied
├── ProviderError
│   ├── RetryableProviderError
│   ├── ContextOverflowError
│   └── FatalProviderError
├── ConfigError
└── StoreError
```

| 처리 위치 | 잡는 오류 | 하는 일 |
|---|---|---|
| Tool Registry | `ToolError` 와 도구 안의 모든 예외 | 도구 결과로 바꿔 LLM에 돌려준다 |
| 어댑터 + Agent Loop | `ProviderError` | 재시도, 압축 후 재전송, 또는 위로 올린다 |
| 인터페이스 | 나머지 | 사용자에게 보여주고 세션을 재개 가능한 상태로 닫는다 |

- 개별 도구는 예외를 잡지 않고 던진다. 변환은 Registry 한곳에서 한다.
- 모든 오류는 이벤트 로그에 남긴다.
- 같은 도구가 같은 오류로 연속 3번 실패하면 루프를 멈춘다.

## 7. 폴더와 권한

| 폴더 | 위치 | 역할 |
|---|---|---|
| 데이터 폴더 | `~/.minisius/` | 설정, DB, 기억, 스킬 |
| 작업 폴더 | CLI는 실행한 폴더, Discord는 `~/minisius-workspace/`(설정 가능) | 사용자의 일을 하는 곳 |

```
~/.minisius/
├── config.toml        # 프로바이더, 모델, 작업 폴더, 권한 정책
├── secrets.toml       # API 키, Discord 토큰 (권한 600)
├── minisius.db        # 이벤트 로그, 세션, 예약 작업, FTS
├── memory/USER.md, MEMORY.md
├── skills/<스킬명>/SKILL.md
└── logs/
```

기본 권한 정책은 [PRD.md](PRD.md) FR-07 이 원본이다. 실행 환경은 `local`(기본) 또는 `docker`.

## 8. 프로세스와 명령어

| 명령 | 역할 |
|---|---|
| `minisius` | 현재 폴더에서 대화 |
| `minisius setup` | 온보딩 |
| `minisius gateway` | Discord 봇과 스케줄러 상시 실행 |
| `minisius service install` / `uninstall` / `status` | 서비스 등록 |
| `minisius sessions` | 세션 목록·재개 |
| `minisius eval` | 평가 실행 |

스케줄러는 `gateway` 프로세스 안에서 돈다. CLI와 게이트웨이가 같은 DB를 동시에 쓸 수 있으므로 WAL 모드로 연다.

## 9. 미정

- 이벤트 로그 스키마와 이벤트 타입 목록
- Compaction 전략
- 중단 복구 시 미완료 도구 호출의 재실행 규칙
- 스킬 자가 작성의 트리거와 검증 방법
