"""도구가 선언하는 Action.

도구는 실행 전에 "이 인수로 실행하면 무엇을 건드리는지"를 Action 으로 선언한다.
policy 는 Action 만 보고 판정하고, 이벤트 로그는 선언된 Action 을 그대로 남긴다.
도구, 정책, 이벤트가 모두 쓰는 타입이라 tools 가 아니라 core 에 둔다.

원본은 docs/ARCHITECTURE.md 5.3절.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ActionKind(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    # MCP 도구처럼 무엇을 하는지 알 수 없는 것
    EXTERNAL = "external"


class Action(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ActionKind
    # 경로, 명령어, URL
    target: str
