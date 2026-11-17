"""내부 표준 메시지 포맷 (docs/ARCHITECTURE.md 5.1절)."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from minisius.core.messages import (
    Message,
    OpaquePart,
    TextPart,
    ToolCallPart,
    ToolResultPart,
)


def _assistant_with_everything() -> Message:
    return Message(
        role="assistant",
        parts=[
            OpaquePart(provider="anthropic", data={"type": "thinking", "signature": "abc"}),
            TextPart(text="파일을 읽어 보겠습니다."),
            ToolCallPart(
                id="call_1",
                name="read_file",
                arguments={"path": "a.md", "lines": [1, 20]},
                provider_data={"thought_signature": "xyz"},
            ),
            ToolCallPart(id="call_2", name="list_dir", arguments={}),
        ],
    )


# --- JSON 왕복: 이벤트 로그 저장이 이 동작에 의존한다 ---


def test_assistant_message_survives_json_round_trip() -> None:
    original = _assistant_with_everything()
    restored = Message.model_validate_json(original.model_dump_json())
    assert restored == original
    assert [type(p) for p in restored.parts] == [OpaquePart, TextPart, ToolCallPart, ToolCallPart]


def test_opaque_and_provider_data_are_kept_verbatim() -> None:
    restored = Message.model_validate_json(_assistant_with_everything().model_dump_json())
    opaque, _, call, bare_call = restored.parts
    assert isinstance(opaque, OpaquePart)
    assert opaque.data == {"type": "thinking", "signature": "abc"}
    assert isinstance(call, ToolCallPart)
    assert call.provider_data == {"thought_signature": "xyz"}
    assert call.arguments == {"path": "a.md", "lines": [1, 20]}
    assert isinstance(bare_call, ToolCallPart)
    assert bare_call.provider_data is None


def test_tool_message_survives_json_round_trip() -> None:
    original = Message.tool_results(
        [
            ToolResultPart(tool_call_id="call_1", content="내용"),
            ToolResultPart(tool_call_id="call_2", content="없는 폴더", is_error=True),
        ]
    )
    restored = Message.model_validate_json(original.model_dump_json())
    assert restored == original
    assert [p.is_error for p in restored.parts if isinstance(p, ToolResultPart)] == [False, True]


def test_dumped_json_carries_type_tags() -> None:
    dumped = json.loads(_assistant_with_everything().model_dump_json())
    assert dumped["role"] == "assistant"
    assert [p["type"] for p in dumped["parts"]] == ["opaque", "text", "tool_call", "tool_call"]


# --- 파트 구분 ---


def test_part_class_is_chosen_by_type_tag() -> None:
    message = Message.model_validate(
        {"role": "tool", "parts": [{"type": "tool_result", "tool_call_id": "c", "content": "ok"}]}
    )
    assert message.parts == [ToolResultPart(tool_call_id="c", content="ok")]


@pytest.mark.parametrize(
    "part",
    [
        {"type": "image", "url": "x"},  # 모르는 type
        {"text": "type 이 없다"},
        {"type": "text"},  # 필수 필드 누락
        {"type": "text", "text": "a", "extra": 1},  # 정의에 없는 필드
    ],
)
def test_malformed_part_is_rejected(part: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Message.model_validate({"role": "assistant", "parts": [part]})


# --- 역할과 파트의 조합 ---


@pytest.mark.parametrize(
    ("role", "part"),
    [
        ("user", ToolCallPart(id="c", name="t", arguments={})),
        ("user", ToolResultPart(tool_call_id="c", content="x")),
        ("user", OpaquePart(provider="anthropic", data={})),
        ("assistant", ToolResultPart(tool_call_id="c", content="x")),
        ("tool", TextPart(text="x")),
        ("tool", ToolCallPart(id="c", name="t", arguments={})),
    ],
)
def test_part_that_does_not_fit_role_is_rejected(role: str, part: Any) -> None:
    with pytest.raises(ValidationError, match="넣을 수 없다"):
        Message.model_validate({"role": role, "parts": [part]})


@pytest.mark.parametrize("role", ["user", "tool"])
def test_empty_user_or_tool_message_is_rejected(role: str) -> None:
    with pytest.raises(ValidationError, match="비어 있을 수 없다"):
        Message.model_validate({"role": role, "parts": []})


def test_empty_assistant_message_is_allowed() -> None:
    message = Message(role="assistant", parts=[])
    assert message.text == ""
    assert message.tool_calls == []


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Message.model_validate({"role": "system", "parts": [{"type": "text", "text": "x"}]})


# --- 불변 ---


def test_message_and_parts_cannot_be_reassigned() -> None:
    message = Message.user("안녕")
    with pytest.raises(ValidationError):
        message.role = "assistant"  # type: ignore[misc]  # 불변인지 확인하려고 일부러 대입한다
    part = message.parts[0]
    assert isinstance(part, TextPart)
    with pytest.raises(ValidationError):
        part.text = "바뀜"  # type: ignore[misc]  # 위와 같다


def test_unknown_field_on_message_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Message.model_validate({"role": "user", "parts": [{"type": "text", "text": "x"}], "id": 1})


# --- 편의 기능 ---


def test_user_constructor() -> None:
    assert Message.user("안녕") == Message(role="user", parts=[TextPart(text="안녕")])


def test_text_joins_only_text_parts() -> None:
    message = Message(
        role="assistant",
        parts=[
            TextPart(text="하나, "),
            ToolCallPart(id="c", name="t", arguments={}),
            OpaquePart(provider="anthropic", data={"text": "보이면 안 됨"}),
            TextPart(text="둘"),
        ],
    )
    assert message.text == "하나, 둘"


def test_tool_calls_keep_model_order() -> None:
    assert [c.id for c in _assistant_with_everything().tool_calls] == ["call_1", "call_2"]
    assert Message.user("x").tool_calls == []
