"""scripts/check_architecture.py 가 위반을 실제로 잡는지 확인한다."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_architecture.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_architecture", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load()


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _rule_ids(root: Path) -> list[str]:
    return [v.rule.id for v in checker.check_tree(root)]


def test_clean_tree_has_no_violations(tmp_path: Path) -> None:
    root = tmp_path / "minisius"
    _write(root, "core/loop.py", "from minisius.providers.base import Provider\n")
    _write(root, "providers/anthropic_adapter.py", "import anthropic\n")
    _write(root, "interfaces/cli/app.py", "from minisius.core import loop\n")
    assert _rule_ids(root) == []


def test_sdk_outside_adapter_is_flagged(tmp_path: Path) -> None:
    root = tmp_path / "minisius"
    _write(root, "core/loop.py", "from anthropic import Anthropic\n")
    assert _rule_ids(root) == ["A2-ANTHROPIC"]


def test_core_importing_adapter_or_interface_is_flagged(tmp_path: Path) -> None:
    root = tmp_path / "minisius"
    _write(root, "core/loop.py", "from minisius.providers import gemini_adapter\n")
    _write(root, "core/session.py", "from ..interfaces import cli\n")
    assert sorted(_rule_ids(root)) == ["A3", "A4"]


def test_tool_spawning_process_or_reading_policy_is_flagged(tmp_path: Path) -> None:
    root = tmp_path / "minisius"
    _write(root, "tools/shell.py", "import subprocess\nfrom minisius.policy import engine\n")
    _write(root, "tools/web.py", "import asyncio\nrun = asyncio.create_subprocess_exec\n")
    assert sorted(_rule_ids(root)) == ["A5", "A5", "A6"]


def test_framework_import_is_flagged(tmp_path: Path) -> None:
    root = tmp_path / "minisius"
    _write(root, "memory/store.py", "from langgraph.graph import StateGraph\n")
    assert _rule_ids(root) == ["A1"]
