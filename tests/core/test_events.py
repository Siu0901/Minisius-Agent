"""이벤트 타입과 이벤트에서 만들어 내는 대화·사용량 (docs/ARCHITECTURE.md 5.6절)."""

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from minisius.core.actions import Action, ActionKind
from minisius.core.events import (
    ErrorOccurred,
    Event,
    EventPayload,
    LLMRequested,
    LLMResponded,
    SessionStarted,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    Usage,
    UserMessage,
    messages_from_events,
    usage_from_events,
)
from minisius.core.messages import Message, TextPart, ToolCallPart, ToolResultPart

PAYLOAD: TypeAdapter[EventPayload] = TypeAdapter(EventPayload)


def _events(*payloads: EventPayload) -> list[Event]:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Event(session_id="s", seq=seq, ts=ts, payload=payload)
        for seq, payload in enumerate(payloads, start=1)
    ]


def _assistant(text: str, *calls: ToolCallPart) -> Message:
    return Message(role="assistant", parts=[TextPart(text=text), *calls])


def _response(
    message: Message,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    cost_usd: float | None = 0.0,
) -> LLMResponded:
    return LLMResponded(
        message=message,
        stop_reason="end_turn",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        cost_usd=cost_usd,
        duration_ms=10,
    )


def _finished(tool_call_id: str, content: str, *, is_error: bool = False) -> ToolCallFinished:
    return ToolCallFinished(
        tool_call_id=tool_call_id, content=content, is_error=is_error, duration_ms=1
    )


# --- 타입 ---


def test_event_type_comes_from_its_payload() -> None:
    (event,) = _events(TurnFinished(reason="completed"))
    assert event.type == "turn_finished"


def test_payload_type_is_chosen_by_the_type_field() -> None:
    payload = PAYLOAD.validate_python({"type": "error", "kind": "X", "message": "m", "fatal": True})
    assert isinstance(payload, ErrorOccurred)


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PAYLOAD.validate_python({"type": "approval_requested"})


@pytest.mark.parametrize(
    "data",
    [
        {"type": "turn_finished", "reason": "bored"},
        {"type": "turn_finished", "reason": "completed", "extra": 1},
        {"type": "llm_request", "model": "m", "message_count": -1},
        {"type": "tool_call_finished", "tool_call_id": "c", "content": "x", "duration_ms": -5},
        {"type": "tool_call_started", "tool_call_id": "c", "name": "n", "arguments": {}},
    ],
)
def test_invalid_payload_is_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PAYLOAD.validate_python(data)


def test_seq_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        Event(
            session_id="s",
            seq=0,
            ts=datetime(2026, 1, 1, tzinfo=UTC),
            payload=TurnFinished(reason="completed"),
        )


def test_events_are_immutable() -> None:
    (event,) = _events(TurnFinished(reason="completed"))
    with pytest.raises(ValidationError):
        event.seq = 9  # type: ignore[misc]  # 고칠 수 없음을 확인한다


# --- 대화 재구성 ---


def test_conversation_is_rebuilt_in_order() -> None:
    call_a = ToolCallPart(id="a", name="list_dir", arguments={"path": "."})
    call_b = ToolCallPart(id="b", name="read_file", arguments={"path": "x.md"})
    user = Message.user("요약해 줘")
    first = _assistant("보겠습니다", call_a, call_b)
    last = _assistant("요약입니다")
    read = Action(kind=ActionKind.READ, target=".")

    events = _events(
        SessionStarted(workdir="/w", provider="anthropic", model="m", interface="cli"),
        UserMessage(message=user),
        LLMRequested(model="m", message_count=1),
        _response(first),
        ToolCallStarted(
            tool_call_id="a", name="list_dir", arguments={"path": "."}, actions=(read,)
        ),
        _finished("a", "x.md"),
        ToolCallStarted(tool_call_id="b", name="read_file", arguments={}, actions=(read,)),
        _finished("b", "없는 파일", is_error=True),
        LLMRequested(model="m", message_count=3),
        _response(last),
        TurnFinished(reason="completed"),
    )

    assert messages_from_events(events) == [
        user,
        first,
        Message.tool_results(
            [
                ToolResultPart(tool_call_id="a", content="x.md"),
                ToolResultPart(tool_call_id="b", content="없는 파일", is_error=True),
            ]
        ),
        last,
    ]


def test_tool_results_at_the_end_are_not_dropped() -> None:
    call = ToolCallPart(id="a", name="t", arguments={})
    events = _events(_response(_assistant("", call)), _finished("a", "결과"))
    assert messages_from_events(events)[-1] == Message.tool_results(
        [ToolResultPart(tool_call_id="a", content="결과")]
    )


def test_interrupted_tool_call_gets_no_invented_result() -> None:
    call = ToolCallPart(id="a", name="t", arguments={})
    response = _assistant("", call)
    events = _events(
        _response(response),
        ToolCallStarted(tool_call_id="a", name="t", arguments={}, actions=()),
    )
    assert messages_from_events(events) == [response]


def test_events_without_messages_produce_no_conversation() -> None:
    events = _events(
        SessionStarted(workdir="/w", provider="p", model="m", interface="cli"),
        ErrorOccurred(kind="FatalProviderError", message="m", fatal=True),
        TurnFinished(reason="fatal_error"),
    )
    assert messages_from_events(events) == []


# --- 사용량 ---


def test_usage_is_summed_over_llm_responses() -> None:
    events = _events(
        UserMessage(message=Message.user("hi")),
        _response(
            _assistant("a"),
            input_tokens=100,
            output_tokens=20,
            cache_read_tokens=5,
            cache_write_tokens=7,
            cost_usd=0.25,
        ),
        _response(_assistant("b"), input_tokens=300, output_tokens=40, cost_usd=0.5),
        TurnFinished(reason="completed"),
    )
    assert usage_from_events(events) == Usage(
        llm_calls=2,
        input_tokens=400,
        output_tokens=60,
        cache_read_tokens=5,
        cache_write_tokens=7,
        cost_usd=0.75,
        unpriced_calls=0,
    )


def test_calls_without_a_known_price_are_counted_separately() -> None:
    events = _events(
        _response(_assistant("a"), input_tokens=1, cost_usd=0.5),
        _response(_assistant("b"), input_tokens=1, cost_usd=None),
    )
    usage = usage_from_events(events)
    assert usage.cost_usd == 0.5
    assert usage.unpriced_calls == 1
    assert usage.llm_calls == 2


def test_usage_of_no_events_is_zero() -> None:
    assert usage_from_events([]) == Usage()
