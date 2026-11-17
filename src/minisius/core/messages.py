"""내부 표준 메시지 포맷. 런타임과 이벤트 로그는 이 타입만 쓴다.

프로바이더별 포맷과의 변환은 각 어댑터가 한다. 원본은 docs/ARCHITECTURE.md 5.1절.
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    # 메시지는 이벤트 로그에 남는 기록이다. 만든 뒤에 바뀌면 안 되고, 모르는 필드는 버그다.
    model_config = ConfigDict(frozen=True, extra="forbid")


class TextPart(_Model):
    type: Literal["text"] = "text"
    text: str


class ToolCallPart(_Model):
    type: Literal["tool_call"] = "tool_call"
    # 어댑터가 항상 고유 값을 보장한다. 프로바이더가 ID 를 주지 않으면 어댑터가 만든다.
    id: str
    name: str
    arguments: dict[str, Any]
    # 이 호출에 붙어 온 프로바이더 원본(예: Gemini thought signature).
    # 같은 프로바이더에만 되돌려 보낸다.
    provider_data: dict[str, Any] | None = None


class ToolResultPart(_Model):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    content: str
    is_error: bool = False


class OpaquePart(_Model):
    """런타임이 해석하지 않고 그대로 되돌려 보내는 프로바이더 원본(예: Anthropic thinking 블록)."""

    type: Literal["opaque"] = "opaque"
    provider: str
    data: dict[str, Any]


Part = Annotated[TextPart | ToolCallPart | ToolResultPart | OpaquePart, Field(discriminator="type")]

Role = Literal["user", "assistant", "tool"]

# 역할마다 넣을 수 있는 파트. 새 파트(예: 이미지)를 추가하면 여기도 고친다.
_ALLOWED_PARTS: dict[Role, tuple[type[_Model], ...]] = {
    "user": (TextPart,),
    "assistant": (TextPart, ToolCallPart, OpaquePart),
    "tool": (ToolResultPart,),
}


class Message(_Model):
    role: Role
    parts: list[Part]

    @model_validator(mode="after")
    def _parts_fit_role(self) -> Self:
        allowed = _ALLOWED_PARTS[self.role]
        for part in self.parts:
            if not isinstance(part, allowed):
                raise ValueError(f"{self.role} 메시지에 {part.type} 파트를 넣을 수 없다")
        # assistant 는 모델이 아무 내용 없이 응답을 끝내는 경우가 있어 빈 것을 허용한다.
        if self.role != "assistant" and not self.parts:
            raise ValueError(f"{self.role} 메시지는 비어 있을 수 없다")
        return self

    @classmethod
    def user(cls, text: str) -> Self:
        return cls(role="user", parts=[TextPart(text=text)])

    @classmethod
    def tool_results(cls, results: list[ToolResultPart]) -> Self:
        return cls(role="tool", parts=list(results))

    @property
    def text(self) -> str:
        """텍스트 파트만 이어 붙인 것."""
        return "".join(part.text for part in self.parts if isinstance(part, TextPart))

    @property
    def tool_calls(self) -> list[ToolCallPart]:
        """도구 호출 파트. 모델이 낸 순서 그대로."""
        return [part for part in self.parts if isinstance(part, ToolCallPart)]
