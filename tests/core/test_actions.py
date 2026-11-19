"""Action (docs/ARCHITECTURE.md 5.3절)."""

import pytest
from pydantic import ValidationError

from minisius.core.actions import Action, ActionKind


def test_action_kind_is_validated_from_its_string_value() -> None:
    action = Action.model_validate({"kind": "write", "target": "/tmp/a.txt"})
    assert action.kind is ActionKind.WRITE


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Action.model_validate({"kind": "format_disk", "target": "/"})


def test_action_is_immutable_and_rejects_unknown_fields() -> None:
    action = Action(kind=ActionKind.READ, target="a.txt")
    with pytest.raises(ValidationError):
        action.target = "b.txt"  # type: ignore[misc]  # 고칠 수 없음을 확인한다
    with pytest.raises(ValidationError):
        Action.model_validate({"kind": "read", "target": "a.txt", "approved": True})
