#!/usr/bin/env python3
"""아키텍처 규칙 검사기.

docs/ARCHITECTURE.md 의 "의존 규칙" 표를 코드로 강제한다.
규칙을 바꿀 때는 문서의 표와 아래 RULES 를 함께 고친다.

사용법:
    python scripts/check_architecture.py [검사할 패키지 경로]

기본 경로는 src/minisius 이다. 위반이 있으면 종료 코드 1.

한계: import 문과 일부 속성 호출만 본다. 내장 open() 같은 직접 파일 접근은
잡지 못하므로 리뷰(architecture-reviewer)로 보완한다.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

PACKAGE = "minisius"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "src" / PACKAGE


@dataclass(frozen=True)
class Rule:
    id: str
    reason: str
    sources: tuple[str, ...]  # 규칙이 적용되는 모듈 접두사
    forbidden: tuple[str, ...]  # 금지된 import 접두사
    except_sources: tuple[str, ...] = ()  # 규칙에서 빠지는 모듈 접두사
    allowed: tuple[str, ...] = ()  # 금지 접두사 중 예외로 허용하는 것
    forbidden_attrs: tuple[str, ...] = ()  # 금지된 속성 이름 (예: x.create_subprocess_exec)


RULES: tuple[Rule, ...] = (
    Rule(
        id="A1",
        reason="에이전트 프레임워크를 쓰지 않고 런타임을 직접 구현한다",
        sources=(PACKAGE,),
        forbidden=(
            "langchain",
            "langchain_core",
            "langchain_community",
            "langgraph",
            "llama_index",
            "crewai",
            "autogen",
            "semantic_kernel",
        ),
    ),
    Rule(
        id="A2",
        reason="anthropic SDK 는 providers/anthropic_adapter.py 에서만 import 한다",
        sources=(PACKAGE,),
        forbidden=("anthropic",),
        except_sources=(f"{PACKAGE}.providers.anthropic_adapter",),
    ),
    Rule(
        id="A2",
        reason="Gemini SDK 는 providers/gemini_adapter.py 에서만 import 한다",
        sources=(PACKAGE,),
        forbidden=("google.genai", "google.generativeai"),
        except_sources=(f"{PACKAGE}.providers.gemini_adapter",),
    ),
    Rule(
        id="A2",
        reason="openai SDK 는 providers/openai_compat_adapter.py 에서만 import 한다",
        sources=(PACKAGE,),
        forbidden=("openai",),
        except_sources=(f"{PACKAGE}.providers.openai_compat_adapter",),
    ),
    Rule(
        id="A3",
        reason="interfaces 는 최상위 계층이다. 다른 계층이 interfaces 를 import 하지 않는다",
        sources=(PACKAGE,),
        forbidden=(f"{PACKAGE}.interfaces",),
        except_sources=(f"{PACKAGE}.interfaces", f"{PACKAGE}.__main__"),
    ),
    Rule(
        id="A4",
        reason="core 는 Provider 인터페이스(providers.base, providers.models)만 안다",
        sources=(f"{PACKAGE}.core",),
        forbidden=(f"{PACKAGE}.providers",),
        allowed=(f"{PACKAGE}.providers.base", f"{PACKAGE}.providers.models"),
    ),
    Rule(
        id="A5",
        reason="도구는 프로세스를 직접 띄우지 않고 execution 백엔드를 거친다",
        sources=(f"{PACKAGE}.tools",),
        forbidden=("subprocess", "pty", "docker"),
        forbidden_attrs=("create_subprocess_exec", "create_subprocess_shell"),
    ),
    Rule(
        id="A6",
        reason="도구는 권한을 스스로 판정하지 않는다. 판정은 Agent Loop 가 policy 에 묻는다",
        sources=(f"{PACKAGE}.tools",),
        forbidden=(f"{PACKAGE}.policy",),
    ),
)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    rule: Rule
    target: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule.id}] '{self.target}' — {self.rule.reason}"


def _matches(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def module_name(path: Path, root: Path) -> str:
    """root(패키지 디렉터리) 기준 파일 경로를 점 표기 모듈 이름으로 바꾼다."""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join([root.name, *parts])


def _resolve_relative(module: str, is_package: bool, level: int, target: str | None) -> str:
    base = module.split(".")
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join([*base, target] if target else base)


def imported_targets(tree: ast.AST, module: str, is_package: bool) -> list[tuple[int, str]]:
    """(줄 번호, import 대상의 전체 이름) 목록."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                source = _resolve_relative(module, is_package, node.level, node.module)
            else:
                source = node.module or ""
            for alias in node.names:
                name = source if alias.name == "*" else f"{source}.{alias.name}"
                found.append((node.lineno, name))
    return found


def check_file(path: Path, root: Path) -> list[Violation]:
    module = module_name(path, root)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets = imported_targets(tree, module, is_package=path.name == "__init__.py")
    attrs = [(n.lineno, n.attr) for n in ast.walk(tree) if isinstance(n, ast.Attribute)]

    violations: list[Violation] = []
    for rule in RULES:
        if not _matches(module, rule.sources) or _matches(module, rule.except_sources):
            continue
        for line, target in targets:
            if _matches(target, rule.forbidden) and not _matches(target, rule.allowed):
                violations.append(Violation(path, line, rule, target))
        for line, attr in attrs:
            if attr in rule.forbidden_attrs:
                violations.append(Violation(path, line, rule, attr))
    return violations


def check_tree(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        violations.extend(check_file(path, root))
    return sorted(violations, key=lambda v: (str(v.path), v.line))


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_ROOT
    if not root.is_dir():
        print(f"check_architecture: 패키지 경로가 없다: {root}", file=sys.stderr)
        return 2
    violations = check_tree(root)
    for violation in violations:
        print(violation.format())
    if violations:
        print(f"\n아키텍처 위반 {len(violations)}건. 규칙: docs/ARCHITECTURE.md", file=sys.stderr)
        return 1
    print("check_architecture: 위반 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
