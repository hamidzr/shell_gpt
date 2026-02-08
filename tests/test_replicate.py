import subprocess
from pathlib import Path
from unittest.mock import patch

from sgpt.utils import REMOTE_BOOTSTRAP_COMMAND, REMOTE_VERIFY_COMMAND

from .utils import app, cmd_args, runner


@patch("sgpt.utils.subprocess.run")
def test_replicate_success(mock_run, tmp_path: Path):
    config_dir = tmp_path / "shell_gpt"
    config_dir.mkdir()

    args = {"--replicate": "user@example.com"}
    with patch("sgpt.utils.SHELL_GPT_CONFIG_FOLDER", config_dir):
        result = runner.invoke(app, cmd_args(**args))

    assert result.exit_code == 0
    assert "Replication complete." in result.output
    assert mock_run.call_count == 3

    bootstrap_call = mock_run.call_args_list[0]
    assert bootstrap_call.args[0] == [
        "ssh",
        "user@example.com",
        "sh",
        "-lc",
        REMOTE_BOOTSTRAP_COMMAND,
    ]
    assert bootstrap_call.kwargs["check"] is True

    copy_call = mock_run.call_args_list[1]
    assert copy_call.args[0] == [
        "scp",
        "-r",
        str(config_dir),
        "user@example.com:~/.config/",
    ]
    assert copy_call.kwargs["check"] is True

    verify_call = mock_run.call_args_list[2]
    assert verify_call.args[0] == [
        "ssh",
        "user@example.com",
        "sh",
        "-lc",
        REMOTE_VERIFY_COMMAND,
    ]
    assert verify_call.kwargs["check"] is True


@patch("sgpt.utils.subprocess.run")
def test_replicate_rejects_target_with_spaces(mock_run, tmp_path: Path):
    config_dir = tmp_path / "shell_gpt"
    config_dir.mkdir()

    args = {"--replicate": "user @example.com"}
    with patch("sgpt.utils.SHELL_GPT_CONFIG_FOLDER", config_dir):
        result = runner.invoke(app, cmd_args(**args))

    assert result.exit_code == 2
    assert "target cannot contain spaces" in result.output
    mock_run.assert_not_called()


@patch("sgpt.utils.subprocess.run")
def test_replicate_requires_local_config_folder(mock_run, tmp_path: Path):
    config_dir = tmp_path / "missing_config_dir"

    args = {"--replicate": "user@example.com"}
    with patch("sgpt.utils.SHELL_GPT_CONFIG_FOLDER", config_dir):
        result = runner.invoke(app, cmd_args(**args))

    assert result.exit_code == 2
    assert "Local config folder does not exist" in result.output
    mock_run.assert_not_called()


@patch("sgpt.utils.subprocess.run")
def test_replicate_reports_remote_failures(mock_run, tmp_path: Path):
    config_dir = tmp_path / "shell_gpt"
    config_dir.mkdir()

    mock_run.side_effect = subprocess.CalledProcessError(
        1,
        ["ssh", "user@example.com", "bootstrap"],
    )
    args = {"--replicate": "user@example.com"}
    with patch("sgpt.utils.SHELL_GPT_CONFIG_FOLDER", config_dir):
        result = runner.invoke(app, cmd_args(**args))

    assert result.exit_code == 2
    assert "Remote replication failed while running: ssh user@example.com bootstrap" in (
        result.output
    )
