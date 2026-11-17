"""Minisius 의 예외 계층. 예외 클래스는 이 파일에만 둔다.

어디서 잡는지는 docs/ARCHITECTURE.md 6절이 원본이다.
"""


class MinisiusError(Exception):
    """이 프로젝트가 던지는 모든 예외의 뿌리."""


# --- 도구: Registry 가 잡아서 도구 결과로 바꿔 LLM 에 돌려준다 ---


class ToolError(MinisiusError):
    """도구 실행 실패. 메시지는 LLM 이 읽고 다음 행동을 정하므로, 무엇이 왜 실패했는지 적는다."""


class ToolArgumentError(ToolError):
    """인수가 도구의 스키마와 맞지 않는다."""


class ToolTimeoutError(ToolError):
    """도구가 제한 시간 안에 끝나지 않았다."""


class PermissionDenied(ToolError):
    """정책이 차단했거나 사용자가 승인을 거절했다."""


# --- 프로바이더: 어댑터가 던지고 Agent Loop 가 처리한다 ---


class ProviderError(MinisiusError):
    """LLM 호출 실패."""


class RetryableProviderError(ProviderError):
    """잠시 뒤 다시 시도하면 될 수 있다 (429, 5xx, 네트워크)."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        # 서버가 알려준 대기 시간(초). 없으면 루프가 간격을 정한다.
        self.retry_after = retry_after


class ContextOverflowError(ProviderError):
    """요청이 모델의 컨텍스트 크기를 넘었다. 압축한 뒤 다시 보낸다."""


class FatalProviderError(ProviderError):
    """다시 시도해도 소용없다 (인증 실패, 없는 모델, 도구 호출 미지원)."""


# --- 그 밖: 인터페이스까지 올라가 사용자에게 보인다 ---


class ConfigError(MinisiusError):
    """설정이나 키가 없거나 잘못됐다."""


class StoreError(MinisiusError):
    """데이터베이스를 읽거나 쓰지 못했다."""
