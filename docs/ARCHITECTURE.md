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
│   ├── openai_compat_adapter.py   # openai, openrouter, ollama 공용
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
├── policy/                # v0.1-beta
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
| A2-ANTHROPIC | `anthropic` SDK 는 `providers/anthropic_adapter.py` 에서만 import 한다 |
| A2-GEMINI | `google.genai` SDK 는 `providers/gemini_adapter.py` 에서만 import 한다 |
| A2-OPENAI | `openai` SDK 는 `providers/openai_compat_adapter.py` 에서만 import 한다 |
| A3 | `interfaces` 는 최상위 계층이다. `interfaces` 와 `__main__` 외에는 `interfaces` 를 import 하지 않는다 |
| A4 | `core` 는 `providers.base` 와 `providers.models` 만 import 한다. 특정 어댑터를 모른다 |
| A5 | `tools` 는 프로세스를 직접 띄우지 않는다(`subprocess` 등 금지). `execution` 백엔드를 거친다 |
| A6 | `tools` 는 `policy` 를 import 하지 않는다. 권한 판정은 Agent Loop 가 도구 실행 전에 `policy` 에 묻는다 |
| A7 | 예외 클래스는 `errors.py` 에만 정의한다 |

코드로 검사하지 못하는 규칙(리뷰로 확인):
- 도구는 파일을 내장 `open()` 으로 직접 열지 않고 `execution` 백엔드를 거친다.
- 런타임과 이벤트 로그는 내부 표준 메시지 포맷만 쓴다. 프로바이더 포맷이 `core` 로 새지 않는다.

## 4. LLM Provider

- 프로바이더 5개(`anthropic`, `gemini`, `openai`, `openrouter`, `ollama`), 어댑터 3개.
  OpenAI, OpenRouter, Ollama는 `OpenAICompatibleAdapter` 를 같이 쓰고 `base_url` 기본값과 API 키 필수 여부만 다르다.
- 내부 표준 메시지 포맷을 직접 정의하고 어댑터가 양방향으로 변환한다.
- 프로바이더 원본(thinking 블록, thought signature 등)은 불투명 필드에 보존해 그대로 되돌려 보낸다.
- 모델 메타데이터 표에 컨텍스트 크기, 토큰 단가, 도구 호출 지원 여부를 둔다.
- 도구 호출을 못 하는 모델은 시작할 때 오류로 거절한다. 텍스트 파싱 우회로는 만들지 않는다.

## 5. 핵심 인터페이스

아래 타입이 계층 사이의 계약이다. 필드를 바꾸면 이 절을 먼저 고친다. 모두 Pydantic 모델이다.

### 5.1 Message — `core/messages.py`

```python
class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolCallPart(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str  # 어댑터가 항상 고유 값을 보장한다
    name: str
    arguments: dict[str, Any]
    provider_data: dict[str, Any] | None = None  # 예: Gemini thought signature


class ToolResultPart(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    content: str
    is_error: bool = False


class OpaquePart(BaseModel):  # 예: Anthropic thinking 블록
    type: Literal["opaque"] = "opaque"
    provider: str
    data: dict[str, Any]


Part = Annotated[TextPart | ToolCallPart | ToolResultPart | OpaquePart, Field(discriminator="type")]


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    parts: list[Part]
```

- 시스템 프롬프트는 메시지가 아니라 `LLMRequest.system` 이다.
- 도구 결과는 `role="tool"` 메시지로 통일한다. 프로바이더별 위치 차이는 어댑터가 처리한다.
- 불투명 데이터(`OpaquePart`, `provider_data`)는 같은 프로바이더에게만 되돌려 보낸다. 세션 중간에 프로바이더가 바뀌면 버린다.
- 이미지 입력은 없다. 필요해지면 `Part` 에 `ImagePart` 를 추가한다.

### 5.2 Provider — `providers/base.py`

```python
class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class StopReason(StrEnum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"


class LLMRequest(BaseModel):
    model: str
    system: str
    messages: list[Message]
    tools: list[ToolSpec]
    max_tokens: int


class LLMResponse(BaseModel):
    message: Message  # role="assistant"
    stop_reason: StopReason
    usage: Usage


class TextDelta(BaseModel):
    text: str


class Provider(Protocol):
    name: str

    def stream(self, request: LLMRequest) -> AsyncIterator[TextDelta | LLMResponse]: ...
```

- 추상 메서드는 `stream()` 하나다. `TextDelta` 를 내보내다가 마지막에 완성된 `LLMResponse` 를 정확히 한 번 내보낸다.
- 도구 호출 인수는 조각으로 내보내지 않는다. 어댑터가 모아서 완성된 `ToolCallPart` 로 준다.
- 어댑터는 SDK 예외를 `ProviderError` 계층으로 바꿔 던진다.

`providers/models.py` 의 `ModelInfo`: `context_window`, `max_output_tokens`, `supports_tools`, 입력·출력 토큰 단가.
표에 없는 모델(Ollama, OpenRouter 의 임의 모델)은 설정 파일에서 값을 받는다.

### 5.3 Tool — `tools/base.py`

```python
class ActionKind(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    EXTERNAL = "external"  # MCP 도구처럼 내용을 알 수 없는 것


class Action(BaseModel):
    kind: ActionKind
    target: str  # 경로, 명령어, URL


class ToolContext(BaseModel):
    session_id: str
    workdir: Path
    backend: ExecutionBackend


class ToolOutput(BaseModel):
    content: str  # LLM 에 돌려줄 텍스트


class Tool[ArgsT: BaseModel](ABC):
    name: str
    description: str
    args_model: type[ArgsT]  # JSON Schema 생성과 인수 검증에 쓴다

    @abstractmethod
    def actions(self, args: ArgsT) -> list[Action]: ...
    @abstractmethod
    async def run(self, args: ArgsT, ctx: ToolContext) -> ToolOutput: ...
```

- `actions()` 는 아무것도 실행하지 않는다. 이 인수로 실행하면 무엇을 건드리는지 사실만 선언한다.
- 허용·승인·차단은 `policy` 가 Action 만 보고 판정한다. `policy` 는 도구 이름과 인수 구조를 모른다.
- 인수 검증 실패, `run()` 안의 예외, 너무 긴 출력의 잘라내기는 Registry 가 처리한다.

### 5.4 도구 호출 한 번의 흐름

LLM 은 도구를 호출하겠다고 응답하고 결과를 받을 뿐이다. 그 사이의 검사는 전부 Agent Loop 가 한다.

1. LLM 응답에 `ToolCallPart` 가 있다.
2. Agent Loop 가 Registry 로 인수를 검증한다. 실패하면 오류를 도구 결과로 돌려준다.
3. Agent Loop 가 도구의 `actions(args)` 를 부른다.
4. `tool_call_started` 이벤트를 기록한다.
5. Agent Loop 가 Action 을 `policy` 에 넘긴다. 판정은 허용, 승인 필요, 차단 중 하나다.
   v0.1-alpha 에는 읽기 전용 도구만 있고, 쓰기·셸 도구는 정책과 함께 v0.1-beta 에 들어온다.
   승인 필요면 `Frontend.request_approval()` 로 사용자에게 묻는다.
6. 허용 또는 승인이면 `run()` 을 부른다. 거절 또는 차단이면 `PermissionDenied` 를 도구 결과로 만든다.
7. `tool_call_finished` 이벤트를 기록하고 결과를 LLM 에 돌려준다.

### 5.5 ExecutionBackend — `execution/base.py`

```python
class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


class ExecutionBackend(Protocol):
    async def run(self, command: str, *, cwd: Path, timeout: float) -> ExecResult: ...
    async def read_file(self, path: Path) -> bytes: ...
    async def write_file(self, path: Path, data: bytes) -> None: ...
    async def list_dir(self, path: Path) -> list[DirEntry]: ...
    async def stat(self, path: Path) -> FileStat | None: ...
    async def delete(self, path: Path) -> None: ...
```

- 명령이 0이 아닌 코드로 끝나는 것은 예외가 아니라 결과다.
- 백엔드는 권한을 모른다. 가장 아래 계층이다.
- `DirEntry`, `FileStat` 의 필드: 미정 (V01-F09 에서 정한다).

### 5.6 Event — `core/events.py`

```python
class Event(BaseModel):
    session_id: str
    seq: int  # 세션 안에서 1부터 증가
    ts: datetime
    type: str
    payload: dict[str, Any]  # type 별 Pydantic 모델로 검증한다
```

| 타입 | 내용 |
|---|---|
| `session_started` | 작업 폴더, 프로바이더, 모델, 인터페이스 |
| `user_message` | 사용자 메시지 |
| `llm_request` | 모델, 컨텍스트에 포함한 이벤트 범위 |
| `llm_response` | 응답 메시지, 종료 이유, 토큰, 비용, 소요 시간 |
| `tool_call_started` | 호출 ID, 도구 이름, 인수, 선언한 Action |
| `tool_call_finished` | 호출 ID, 결과, 오류 여부, 소요 시간 |
| `error` | 종류, 메시지, 치명 여부 |
| `turn_finished` | 이유: 정상 종료, 횟수 초과, 반복 오류, 취소, 치명 오류 |

- `tool_call_started` 는 실행 전에 기록한다. started 만 있고 finished 가 없는 호출이 중단 지점이다.
- 대화 메시지 목록은 따로 저장하지 않고 이벤트에서 만들어 낸다.
- `TextDelta` 는 이벤트 로그에 남기지 않는다. 완성된 응답만 `llm_response` 로 남긴다.
- 승인(v0.1-beta), 압축(v0.3), 계획(v0.6) 이벤트는 해당 버전에서 추가한다.

### 5.7 Frontend와 Session — `interfaces/base.py`, `core/session.py`

```python
class ApprovalRequest(BaseModel):
    tool_call_id: str
    tool_name: str
    actions: list[Action]


class ApprovalDecision(StrEnum):
    ALLOW_ONCE = "allow_once"
    ALLOW_ALWAYS = "allow_always"
    DENY = "deny"


class Frontend(Protocol):  # 런타임이 인터페이스에 요구하는 것 (v0.1-beta)
    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision: ...


class Session:  # 인터페이스가 호출하는 것
    def run_turn(self, text: str) -> AsyncIterator[Event | TextDelta]: ...
    def cancel(self) -> None: ...
```

인터페이스는 `run_turn()` 의 스트림을 받아 그리기만 한다. 런타임 로직을 인터페이스에 두지 않는다.

### 5.8 중단된 도구 호출

프로세스가 죽은 뒤 이벤트 로그를 읽으면 도구 호출은 셋 중 하나다.

| 로그의 상태 | 의미 | 처리 |
|---|---|---|
| `tool_call_started` 없음 | 실행하지 않았다 | 다시 실행해도 된다 |
| started 와 finished 둘 다 있음 | 끝났다 | 다시 실행하지 않는다 |
| started 만 있음 | **결과를 모른다.** 실행 전에 죽었을 수도, 실행은 끝났는데 기록 전에 죽었을 수도 있다 | 자동으로 다시 실행하지 않는다 |

started 만 있는 호출은 "안 했다"가 아니라 "모른다"로 다룬다. 기본 정책은 자동 재실행 금지다.
현재 상태를 확인하거나 사용자에게 묻는 구체적인 복구 방법은 v0.6 에서 정한다.

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

- 이벤트 로그의 SQLite 스키마, 이벤트 타입별 payload 필드
- Compaction 전략
- 결과가 불확실한 도구 호출을 복구하는 구체적인 방법 (기본 정책은 5.8절)
- 스킬 자가 작성의 트리거와 검증 방법
