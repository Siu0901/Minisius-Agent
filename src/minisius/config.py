"""설정과 경로 규칙.

- 데이터 폴더: 환경 변수 MINISIUS_HOME, 없으면 ~/.minisius
- 설정: <데이터 폴더>/config.toml
- 비밀 값: <데이터 폴더>/.env. 같은 이름의 환경 변수가 있으면 그쪽이 우선한다.

원본은 docs/ARCHITECTURE.md 7절.
"""

import os
import stat
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from minisius.errors import ConfigError

HOME_ENV = "MINISIUS_HOME"

Provider = Literal["anthropic", "gemini", "openai", "openrouter", "ollama"]


API_KEY_ENV: dict[Provider, str | None] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama": None,
}

_EXAMPLE_CONFIG = """\
[llm]
provider = "anthropic"
model = "<모델 이름>"
"""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Paths(_Model):
    home: Path
    config_file: Path
    env_file: Path
    db_file: Path
    memory_dir: Path
    skills_dir: Path
    logs_dir: Path

    @classmethod
    def from_home(cls, home: Path) -> Self:
        return cls(
            home=home,
            config_file=home / "config.toml",
            env_file=home / ".env",
            db_file=home / "minisius.db",
            memory_dir=home / "memory",
            skills_dir=home / "skills",
            logs_dir=home / "logs",
        )


class LLMSettings(_Model):
    # 모델 이름은 금방 낡으므로 기본값을 두지 않는다.
    provider: Provider
    model: str = Field(min_length=1)
    max_tokens: int = Field(default=8192, gt=0)


class AgentSettings(_Model):
    max_iterations: int = Field(default=50, gt=0)


class ExecutionSettings(_Model):
    backend: Literal["local", "docker"] = "local"


class _ConfigFile(_Model):
    """config.toml 의 모양. 새 섹션은 그 기능을 만들 때 추가한다."""

    llm: LLMSettings
    agent: AgentSettings = AgentSettings()
    execution: ExecutionSettings = ExecutionSettings()


class Settings(_Model):
    paths: Paths
    llm: LLMSettings
    agent: AgentSettings
    execution: ExecutionSettings
    api_key: SecretStr | None
    # 시작은 막지 않지만 사용자에게 보여줄 것. 인터페이스가 출력한다.
    warnings: tuple[str, ...] = ()


def resolve_home(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    custom = env.get(HOME_ENV)
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".minisius"


def load_settings(home: Path | None = None, *, env: Mapping[str, str] | None = None) -> Settings:
    """설정을 읽는다. 문제가 있으면 무엇을 고쳐야 하는지 적은 ConfigError 를 던진다."""
    env = os.environ if env is None else env
    paths = Paths.from_home(home if home is not None else resolve_home(env))

    config = _read_config(paths.config_file)
    file_secrets, warnings = _read_env_file(paths.env_file)
    api_key = _find_api_key(config.llm.provider, env, file_secrets, paths.env_file)

    return Settings(
        paths=paths,
        llm=config.llm,
        agent=config.agent,
        execution=config.execution,
        api_key=api_key,
        warnings=tuple(warnings),
    )


def _read_config(path: Path) -> _ConfigFile:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(
            f"설정 파일이 없습니다: {path}\n아래 내용으로 만드세요.\n\n{_EXAMPLE_CONFIG}"
        ) from None
    except OSError as exc:
        raise ConfigError(f"설정 파일을 읽지 못했습니다: {path} ({exc.strerror})") from exc

    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"설정 파일의 문법이 틀렸습니다: {path}\n{exc}") from exc

    try:
        return _ConfigFile.model_validate(data)
    except ValidationError as exc:
        problems = "\n".join(f"- {_describe(error)}" for error in exc.errors())
        raise ConfigError(f"설정 파일에 문제가 있습니다: {path}\n{problems}") from None


def _describe(error: Any) -> str:
    """pydantic 오류 하나를 한 줄로. 입력 값은 넣지 않는다.

    사용자가 API 키를 config.toml 에 잘못 적었을 때 오류 메시지로 키가 새지 않게 한다.
    """
    section, *rest = (str(part) for part in error["loc"])
    where = f"[{section}]" + (f" {'.'.join(rest)}" if rest else "")
    kind = error["type"]
    if kind == "missing":
        return f"{where}: 필수 항목이 없습니다"
    if kind == "extra_forbidden":
        return f"{where}: 모르는 항목입니다"
    return f"{where}: {error['msg']}"


def _read_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    if not path.is_file():
        return {}, []
    warnings: list[str] = []
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        warnings.append(
            f"{path} 를 이 컴퓨터의 다른 사용자가 읽을 수 있습니다. "
            f"`chmod 600 {path}` 로 권한을 좁히세요."
        )
    try:
        values = dotenv_values(path, encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"키 파일을 읽지 못했습니다: {path} ({exc.strerror})") from exc
    return {name: value for name, value in values.items() if value}, warnings


def _find_api_key(
    provider: Provider, env: Mapping[str, str], file_secrets: Mapping[str, str], env_file: Path
) -> SecretStr | None:
    name = API_KEY_ENV[provider]
    if name is None:
        return None
    # 환경 변수가 파일보다 우선한다. 빈 문자열은 없는 것으로 본다.
    value = env.get(name) or file_secrets.get(name)
    if not value:
        raise ConfigError(
            f"{provider} 의 API 키가 없습니다. "
            f"{env_file} 에 `{name}=...` 을 적거나 환경 변수 {name} 을 설정하세요."
        )
    return SecretStr(value)
