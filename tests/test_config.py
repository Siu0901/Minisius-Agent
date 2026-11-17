"""설정과 경로 규칙 (docs/ARCHITECTURE.md 7절).

모든 테스트는 tmp_path 와 직접 넘긴 env 만 쓴다. 실제 ~/.minisius 와 실제 환경 변수를 읽지 않는다.
"""

import os
from pathlib import Path

import pytest

from minisius.config import HOME_ENV, Paths, load_settings, resolve_home
from minisius.errors import ConfigError

MINIMAL = '[llm]\nprovider = "anthropic"\nmodel = "some-model"\n'
SECRET = "sk-test-do-not-print"


def _home(tmp_path: Path, config: str | None = MINIMAL, dotenv: str | None = None) -> Path:
    if config is not None:
        (tmp_path / "config.toml").write_text(config, encoding="utf-8")
    if dotenv is not None:
        env_file = tmp_path / ".env"
        env_file.write_text(dotenv, encoding="utf-8")
        env_file.chmod(0o600)
    return tmp_path


# --- 경로 ---


def test_home_comes_from_env_variable(tmp_path: Path) -> None:
    assert resolve_home({HOME_ENV: str(tmp_path)}) == tmp_path


def test_home_expands_tilde() -> None:
    assert resolve_home({HOME_ENV: "~/somewhere"}) == Path.home() / "somewhere"


@pytest.mark.parametrize("env", [{}, {HOME_ENV: ""}])
def test_home_defaults_to_dot_minisius(env: dict[str, str]) -> None:
    assert resolve_home(env) == Path.home() / ".minisius"


def test_paths_are_derived_from_home(tmp_path: Path) -> None:
    paths = Paths.from_home(tmp_path)
    assert paths.config_file == tmp_path / "config.toml"
    assert paths.env_file == tmp_path / ".env"
    assert paths.db_file == tmp_path / "minisius.db"
    assert paths.memory_dir == tmp_path / "memory"
    assert paths.skills_dir == tmp_path / "skills"
    assert paths.logs_dir == tmp_path / "logs"


def test_load_settings_uses_home_from_env_when_not_given(tmp_path: Path) -> None:
    _home(tmp_path)
    settings = load_settings(env={HOME_ENV: str(tmp_path), "ANTHROPIC_API_KEY": SECRET})
    assert settings.paths.home == tmp_path


# --- 올바른 설정 ---


def test_minimal_config_gets_defaults(tmp_path: Path) -> None:
    settings = load_settings(_home(tmp_path), env={"ANTHROPIC_API_KEY": SECRET})
    assert settings.llm.provider == "anthropic"
    assert settings.llm.model == "some-model"
    assert settings.llm.max_tokens == 8192
    assert settings.agent.max_iterations == 50
    assert settings.execution.backend == "local"
    assert settings.warnings == ()


def test_full_config_overrides_defaults(tmp_path: Path) -> None:
    config = (
        '[llm]\nprovider = "gemini"\nmodel = "g"\nmax_tokens = 1000\n'
        "[agent]\nmax_iterations = 7\n"
        '[execution]\nbackend = "docker"\n'
    )
    settings = load_settings(_home(tmp_path, config), env={"GEMINI_API_KEY": SECRET})
    assert settings.llm.max_tokens == 1000
    assert settings.agent.max_iterations == 7
    assert settings.execution.backend == "docker"


# --- 잘못된 설정 ---


def test_missing_config_file_explains_how_to_create_it(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        load_settings(_home(tmp_path, config=None), env={})
    message = str(caught.value)
    assert str(tmp_path / "config.toml") in message
    assert "[llm]" in message


def test_toml_syntax_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="문법"):
        load_settings(_home(tmp_path, "[llm\nprovider = "), env={})


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ("[agent]\nmax_iterations = 3\n", "[llm]: 필수 항목이 없습니다"),
        ('[llm]\nprovider = "anthropic"\n', "[llm] model: 필수 항목이 없습니다"),
        (MINIMAL + "modle = 1\n", "[llm] modle: 모르는 항목입니다"),
        (MINIMAL + "[discord]\ntoken = 1\n", "[discord]: 모르는 항목입니다"),
        ('[llm]\nprovider = "clod"\nmodel = "m"\n', "[llm] provider:"),
        ('[llm]\nprovider = "anthropic"\nmodel = ""\n', "[llm] model:"),
        (MINIMAL + "max_tokens = 0\n", "[llm] max_tokens:"),
        (MINIMAL + '[agent]\nmax_iterations = "many"\n', "[agent] max_iterations:"),
        (MINIMAL + '[execution]\nbackend = "ssh"\n', "[execution] backend:"),
    ],
)
def test_invalid_config_names_the_offending_key(tmp_path: Path, config: str, expected: str) -> None:
    with pytest.raises(ConfigError) as caught:
        load_settings(_home(tmp_path, config), env={"ANTHROPIC_API_KEY": SECRET})
    assert expected in str(caught.value)


def test_all_problems_are_reported_at_once(tmp_path: Path) -> None:
    config = '[llm]\nprovider = "clod"\nmodle = "m"\n'
    with pytest.raises(ConfigError) as caught:
        load_settings(_home(tmp_path, config), env={})
    message = str(caught.value)
    assert "[llm] provider:" in message
    assert "[llm] model: 필수 항목이 없습니다" in message
    assert "[llm] modle: 모르는 항목입니다" in message


# --- API 키 ---


def test_key_is_read_from_env_file(tmp_path: Path) -> None:
    settings = load_settings(_home(tmp_path, dotenv=f"ANTHROPIC_API_KEY={SECRET}\n"), env={})
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == SECRET


def test_environment_variable_wins_over_env_file(tmp_path: Path) -> None:
    home = _home(tmp_path, dotenv="ANTHROPIC_API_KEY=from-file\n")
    settings = load_settings(home, env={"ANTHROPIC_API_KEY": "from-env"})
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == "from-env"


def test_empty_environment_variable_falls_back_to_env_file(tmp_path: Path) -> None:
    home = _home(tmp_path, dotenv="ANTHROPIC_API_KEY=from-file\n")
    settings = load_settings(home, env={"ANTHROPIC_API_KEY": ""})
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == "from-file"


@pytest.mark.parametrize("dotenv", [None, "", "ANTHROPIC_API_KEY=\n", "OPENAI_API_KEY=other\n"])
def test_missing_key_says_which_variable_to_set(tmp_path: Path, dotenv: str | None) -> None:
    with pytest.raises(ConfigError) as caught:
        load_settings(_home(tmp_path, dotenv=dotenv), env={})
    message = str(caught.value)
    assert "ANTHROPIC_API_KEY" in message
    assert str(tmp_path / ".env") in message


@pytest.mark.parametrize(
    ("provider", "variable"),
    [
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("openrouter", "OPENROUTER_API_KEY"),
    ],
)
def test_each_provider_reads_its_own_variable(tmp_path: Path, provider: str, variable: str) -> None:
    config = f'[llm]\nprovider = "{provider}"\nmodel = "m"\n'
    others = {"ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"}
    env = {name: "wrong" for name in others - {variable}} | {variable: SECRET}
    settings = load_settings(_home(tmp_path, config), env=env)
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == SECRET


def test_ollama_needs_no_key(tmp_path: Path) -> None:
    config = '[llm]\nprovider = "ollama"\nmodel = "m"\n'
    assert load_settings(_home(tmp_path, config), env={}).api_key is None


# --- 키가 드러나지 않는다 ---


def test_key_is_not_shown_when_settings_are_printed(tmp_path: Path) -> None:
    settings = load_settings(_home(tmp_path), env={"ANTHROPIC_API_KEY": SECRET})
    assert SECRET not in repr(settings)
    assert SECRET not in str(settings)
    assert SECRET not in settings.model_dump_json()


def test_key_written_into_config_file_by_mistake_is_not_echoed(tmp_path: Path) -> None:
    config = MINIMAL + f'api_key = "{SECRET}"\n'
    with pytest.raises(ConfigError) as caught:
        load_settings(_home(tmp_path, config), env={})
    assert "[llm] api_key: 모르는 항목입니다" in str(caught.value)
    assert SECRET not in str(caught.value)
    assert caught.value.__cause__ is None  # 원래 pydantic 오류에는 입력 값이 들어 있다


# --- .env 파일 권한 ---


@pytest.mark.skipif(os.name != "posix", reason="POSIX 권한이 있는 곳에서만 의미가 있다")
def test_env_file_readable_by_others_produces_a_warning(tmp_path: Path) -> None:
    home = _home(tmp_path, dotenv=f"ANTHROPIC_API_KEY={SECRET}\n")
    (home / ".env").chmod(0o644)
    settings = load_settings(home, env={})
    assert len(settings.warnings) == 1
    assert "chmod 600" in settings.warnings[0]
    assert SECRET not in settings.warnings[0]
    assert settings.api_key is not None  # 경고일 뿐 시작은 막지 않는다


@pytest.mark.skipif(os.name != "posix", reason="POSIX 권한이 있는 곳에서만 의미가 있다")
def test_private_env_file_produces_no_warning(tmp_path: Path) -> None:
    settings = load_settings(_home(tmp_path, dotenv=f"ANTHROPIC_API_KEY={SECRET}\n"), env={})
    assert settings.warnings == ()
