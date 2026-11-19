"""이벤트 타입과, 이벤트에서 대화와 사용량을 만들어 내는 함수.

런타임에서 일어나는 일은 전부 이벤트로 남는다. 대화 메시지 목록과 토큰 집계는 따로 저장하지
않고 여기의 함수로 이벤트에서 만들어 낸다. 저장은 store/event_log.py 가 한다.

원본은 docs/ARCHITECTURE.md 5.6절.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from minisius.core.actions import Action
from minisius.core.messages import Message, ToolResultPart


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SessionStarted(_Model):
    type: Literal["session_started"] = "session_started"
    workdir: str
    provider: str
    model: str
    interface: str


class UserMessage(_Model):
    type: Literal["user_message"] = "user_message"
    message: Message


class LLMRequested(_Model):
    """요청을 보내기 직전에 남긴다. 응답 없이 끝난 요청을 찾을 수 있게 한다."""

    type: Literal["llm_request"] = "llm_request"
    model: str
    message_count: int = Field(ge=0)


class LLMResponded(_Model):
    type: Literal["llm_response"] = "llm_response"
    message: Message
    # providers.base.StopReason 과 같은 값이다.
    stop_reason: Literal["end_turn", "tool_use", "max_tokens"]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    # 단가를 모르는 모델이면 None
    cost_usd: float | None = Field(default=None, ge=0)
    duration_ms: int = Field(ge=0)


class ToolCallStarted(_Model):
    """실행 전에 남긴다. 이것만 있고 ToolCallFinished 가 없는 호출은 결과를 모르는 호출이다."""

    type: Literal["tool_call_started"] = "tool_call_started"
    tool_call_id: str
    name: str
    # 걸러내지 않고 그대로 남긴다. 한계는 docs/ARCHITECTURE.md 9절.
    arguments: dict[str, object]
    actions: tuple[Action, ...]


class ToolCallFinished(_Model):
    type: Literal["tool_call_finished"] = "tool_call_finished"
    tool_call_id: str
    # LLM 에 돌려준 그대로
    content: str
    is_error: bool = False
    duration_ms: int = Field(ge=0)


class ErrorOccurred(_Model):
    type: Literal["error"] = "error"
    kind: str
    message: str
    fatal: bool


TurnEndReason = Literal["completed", "max_iterations", "repeated_error", "cancelled", "fatal_error"]


class TurnFinished(_Model):
    type: Literal["turn_finished"] = "turn_finished"
    reason: TurnEndReason


EventPayload = Annotated[
    SessionStarted
    | UserMessage
    | LLMRequested
    | LLMResponded
    | ToolCallStarted
    | ToolCallFinished
    | ErrorOccurred
    | TurnFinished,
    Field(discriminator="type"),
]


class Event(_Model):
    session_id: str
    # 세션 안에서 1부터 증가. 이벤트 로그가 매긴다.
    seq: int = Field(ge=1)
    ts: datetime
    payload: EventPayload

    @property
    def type(self) -> str:
        return self.payload.type


class Usage(_Model):
    """세션 하나의 사용량 합계."""

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    # 단가를 몰라 cost_usd 에 들어가지 않은 호출 수. 0 이 아니면 비용은 실제보다 적다.
    unpriced_calls: int = 0


def messages_from_events(events: Iterable[Event]) -> list[Message]:
    """이벤트에서 LLM 에 보낼 대화를 순서대로 만든다.

    잇달아 끝난 도구 호출의 결과는 tool 메시지 하나로 묶는다. 프로바이더가 한 응답의 도구 호출
    결과를 한 메시지로 받기 때문이다.

    결과 없이 끝난 도구 호출(started 만 있음)은 채우지 않는다. 그 처리는 세션 재개가 정한다.
    """
    messages: list[Message] = []
    pending: list[ToolResultPart] = []

    def flush() -> None:
        if pending:
            messages.append(Message.tool_results(list(pending)))
            pending.clear()

    for event in events:
        payload = event.payload
        if isinstance(payload, ToolCallFinished):
            pending.append(
                ToolResultPart(
                    tool_call_id=payload.tool_call_id,
                    content=payload.content,
                    is_error=payload.is_error,
                )
            )
        elif isinstance(payload, UserMessage | LLMResponded):
            flush()
            messages.append(payload.message)
    flush()
    return messages


def usage_from_events(events: Iterable[Event]) -> Usage:
    responses = [e.payload for e in events if isinstance(e.payload, LLMResponded)]
    return Usage(
        llm_calls=len(responses),
        input_tokens=sum(r.input_tokens for r in responses),
        output_tokens=sum(r.output_tokens for r in responses),
        cache_read_tokens=sum(r.cache_read_tokens for r in responses),
        cache_write_tokens=sum(r.cache_write_tokens for r in responses),
        cost_usd=sum(r.cost_usd for r in responses if r.cost_usd is not None),
        unpriced_calls=sum(1 for r in responses if r.cost_usd is None),
    )
