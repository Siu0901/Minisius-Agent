"""예외 계층이 docs/ARCHITECTURE.md 6절과 같은지 확인한다."""

import inspect

import pytest

from minisius import errors


@pytest.mark.parametrize(
    ("child", "parent"),
    [
        (errors.MinisiusError, Exception),
        (errors.ToolError, errors.MinisiusError),
        (errors.ToolArgumentError, errors.ToolError),
        (errors.ToolTimeoutError, errors.ToolError),
        (errors.PermissionDenied, errors.ToolError),
        (errors.ProviderError, errors.MinisiusError),
        (errors.RetryableProviderError, errors.ProviderError),
        (errors.ContextOverflowError, errors.ProviderError),
        (errors.FatalProviderError, errors.ProviderError),
        (errors.ConfigError, errors.MinisiusError),
        (errors.StoreError, errors.MinisiusError),
    ],
)
def test_hierarchy_matches_architecture(child: type, parent: type) -> None:
    assert issubclass(child, parent)


def test_module_defines_exactly_the_documented_exceptions() -> None:
    defined = {
        name
        for name, cls in inspect.getmembers(errors, inspect.isclass)
        if cls.__module__ == errors.__name__
    }
    assert defined == {
        "MinisiusError",
        "ToolError",
        "ToolArgumentError",
        "ToolTimeoutError",
        "PermissionDenied",
        "ProviderError",
        "RetryableProviderError",
        "ContextOverflowError",
        "FatalProviderError",
        "ConfigError",
        "StoreError",
    }


def test_tool_and_provider_branches_are_separate() -> None:
    # Registry 가 ToolError 를 잡을 때 프로바이더 오류까지 삼키면 안 된다.
    assert not issubclass(errors.ProviderError, errors.ToolError)
    assert not issubclass(errors.ToolError, errors.ProviderError)


def test_catching_tool_error_does_not_catch_provider_error() -> None:
    with pytest.raises(errors.FatalProviderError):
        try:
            raise errors.FatalProviderError("인증 실패")
        except errors.ToolError:
            pytest.fail("ToolError 처리기가 프로바이더 오류를 잡았다")


def test_retry_after_is_kept() -> None:
    error = errors.RetryableProviderError("429", retry_after=2.5)
    assert error.retry_after == 2.5
    assert str(error) == "429"
    assert errors.RetryableProviderError("timeout").retry_after is None
