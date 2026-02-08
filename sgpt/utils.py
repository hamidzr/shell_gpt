import os
import platform
import shlex
import subprocess
from tempfile import NamedTemporaryFile
from typing import Any, Callable

import typer
from click import BadParameter, UsageError

from sgpt.__version__ import __version__
from sgpt.config import SHELL_GPT_CONFIG_FOLDER
from sgpt.integration import bash_integration, zsh_integration


def get_edited_prompt() -> str:
    """
    Opens the user's default editor to let them
    input a prompt, and returns the edited text.

    :return: String prompt.
    """
    with NamedTemporaryFile(suffix=".txt", delete=False) as file:
        # Create file and store path.
        file_path = file.name
    editor = os.environ.get("EDITOR", "vim")
    # This will write text to file using $EDITOR.
    os.system(f"{editor} {file_path}")
    # Read file when editor is closed.
    with open(file_path, "r", encoding="utf-8") as file:
        output = file.read()
    os.remove(file_path)
    if not output:
        raise BadParameter("Couldn't get valid PROMPT from $EDITOR")
    return output


def run_command(command: str) -> None:
    """
    Runs a command in the user's shell.
    It is aware of the current user's $SHELL.
    :param command: A shell command to run.
    """
    if platform.system() == "Windows":
        is_powershell = len(os.getenv("PSModulePath", "").split(os.pathsep)) >= 3
        full_command = (
            f'powershell.exe -Command "{command}"'
            if is_powershell
            else f'cmd.exe /c "{command}"'
        )
    else:
        shell = os.environ.get("SHELL", "/bin/sh")
        full_command = f"{shell} -c {shlex.quote(command)}"

    os.system(full_command)


REMOTE_BOOTSTRAP_COMMAND = (
    "set -eu; "
    "mkdir -p \"$HOME/.config\" \"$HOME/.local/bin\"; "
    "if ! command -v uv >/dev/null 2>&1 && [ ! -x \"$HOME/.local/bin/uv\" ]; then "
    "if command -v curl >/dev/null 2>&1; then "
    "curl -LsSf https://astral.sh/uv/install.sh | sh; "
    "elif command -v wget >/dev/null 2>&1; then "
    "wget -qO- https://astral.sh/uv/install.sh | sh; "
    "else echo 'missing curl or wget for uv install' >&2; exit 1; "
    "fi; "
    "fi; "
    "UV_BIN=\"$(command -v uv || true)\"; "
    "if [ -z \"$UV_BIN\" ] && [ -x \"$HOME/.local/bin/uv\" ]; then "
    "UV_BIN=\"$HOME/.local/bin/uv\"; "
    "fi; "
    "if [ -z \"$UV_BIN\" ]; then "
    "echo 'uv installation failed' >&2; exit 1; "
    "fi; "
    "\"$UV_BIN\" tool install --force shell-gpt"
)
REMOTE_VERIFY_COMMAND = (
    "set -eu; "
    "if [ -d \"$HOME/.config/shell_gpt\" ]; then "
    "chmod -R go-rwx \"$HOME/.config/shell_gpt\" 2>/dev/null || true; "
    "fi; "
    "if [ -x \"$HOME/.local/bin/sgpt\" ]; then "
    "\"$HOME/.local/bin/sgpt\" --version; "
    "elif command -v sgpt >/dev/null 2>&1; then "
    "sgpt --version; "
    "else "
    "echo 'shell-gpt installed but sgpt is not in PATH, use $HOME/.local/bin/sgpt' >&2; "
    "exit 1; "
    "fi"
)


def replicate_to_host(target: str) -> None:
    """
    Installs shell-gpt on remote host with uv and copies local config over SSH.
    """
    if platform.system() == "Windows":
        raise UsageError("`--replicate` is only available on POSIX systems.")

    normalized_target = target.strip()
    if not normalized_target:
        raise UsageError("`--replicate` requires a target in the form user@host.")
    if normalized_target.startswith("-"):
        raise UsageError("`--replicate` target cannot start with '-'.")
    if any(char.isspace() for char in normalized_target):
        raise UsageError("`--replicate` target cannot contain spaces.")

    if not SHELL_GPT_CONFIG_FOLDER.exists():
        raise UsageError(
            f"Local config folder does not exist: {SHELL_GPT_CONFIG_FOLDER}"
        )

    try:
        typer.echo(f"Bootstrapping ShellGPT on {normalized_target}...")
        subprocess.run(
            ["ssh", normalized_target, "sh", "-lc", REMOTE_BOOTSTRAP_COMMAND],
            check=True,
        )

        typer.echo(
            f"Copying local config from {SHELL_GPT_CONFIG_FOLDER} to remote host..."
        )
        subprocess.run(
            [
                "scp",
                "-r",
                str(SHELL_GPT_CONFIG_FOLDER),
                f"{normalized_target}:~/.config/",
            ],
            check=True,
        )

        typer.echo("Verifying remote installation...")
        subprocess.run(
            ["ssh", normalized_target, "sh", "-lc", REMOTE_VERIFY_COMMAND],
            check=True,
        )
    except FileNotFoundError as err:
        missing = err.filename or "unknown"
        raise UsageError(f"Required command not found: {missing}") from err
    except subprocess.CalledProcessError as err:
        command = err.cmd if isinstance(err.cmd, str) else " ".join(err.cmd)
        raise UsageError(f"Remote replication failed while running: {command}") from err

    typer.echo("Replication complete.")


def option_callback(func: Callable) -> Callable:  # type: ignore
    def wrapper(cls: Any, value: str) -> None:
        if not value:
            return
        func(cls, value)
        raise typer.Exit()

    return wrapper


@option_callback
def install_shell_integration(*_args: Any) -> None:
    """
    Installs shell integration. Currently only supports ZSH and Bash.
    Allows user to get shell completions in terminal by using hotkey.
    Replaces current "buffer" of the shell with the completion.
    """
    # TODO: Add support for Windows.
    # TODO: Implement updates.
    shell = os.getenv("SHELL", "")
    if "zsh" in shell:
        typer.echo("Installing ZSH integration...")
        with open(os.path.expanduser("~/.zshrc"), "a", encoding="utf-8") as file:
            file.write(zsh_integration)
    elif "bash" in shell:
        typer.echo("Installing Bash integration...")
        with open(os.path.expanduser("~/.bashrc"), "a", encoding="utf-8") as file:
            file.write(bash_integration)
    else:
        raise UsageError("ShellGPT integrations only available for ZSH and Bash.")

    typer.echo("Done! Restart your shell to apply changes.")


@option_callback
def get_sgpt_version(*_args: Any) -> None:
    """
    Displays the current installed version of ShellGPT
    """
    typer.echo(f"ShellGPT {__version__}")
