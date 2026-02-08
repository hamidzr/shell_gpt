from pathlib import Path

import pytest

from sgpt.config import Config


@pytest.mark.parametrize(
    "key,suffix",
    [
        ("ROLE_STORAGE_PATH", "roles"),
        ("OPENAI_FUNCTIONS_PATH", "functions"),
        ("CHAT_CACHE_PATH", "chat_cache"),
        ("CACHE_PATH", "cache"),
    ],
)
@pytest.mark.parametrize("raw_prefix", ["~", "$HOME"])
def test_path_keys_expand_home_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    suffix: str,
    raw_prefix: str,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    config_path = tmp_path / ".sgptrc"
    config_path.write_text(f"{key}={raw_prefix}/shell_gpt/{suffix}\n", encoding="utf-8")

    config = Config(config_path)

    assert config.get(key) == str(home / "shell_gpt" / suffix)


def test_path_keys_expand_home_from_env_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    config_path = tmp_path / ".sgptrc"
    config_path.write_text("ROLE_STORAGE_PATH=/tmp/ignored\n", encoding="utf-8")
    monkeypatch.setenv("ROLE_STORAGE_PATH", "$HOME/override/roles")

    config = Config(config_path)

    assert config.get("ROLE_STORAGE_PATH") == str(home / "override" / "roles")


def test_non_path_key_keeps_literal_value(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".sgptrc"
    config_path.write_text("DEFAULT_MODEL=$HOME/literal-model\n", encoding="utf-8")

    config = Config(config_path)

    assert config.get("DEFAULT_MODEL") == "$HOME/literal-model"
