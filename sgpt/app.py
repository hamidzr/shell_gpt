import os
import sys
from pathlib import Path

import typer
from click import UsageError
from click.types import Choice

from sgpt.utils import (
    get_edited_prompt,
    get_sgpt_version,
    install_shell_integration,
    run_command,
)


def list_chats_callback(value: bool) -> None:
    if not value:
        return

    from sgpt.config import cfg

    chat_cache_path = Path(cfg.get("CHAT_CACHE_PATH"))
    if chat_cache_path.exists():
        for chat_id in sorted(chat_cache_path.glob("*"), key=lambda p: p.stat().st_mtime):
            typer.echo(chat_id)
    raise typer.Exit()


def create_role_callback(value: str | None) -> None:
    if not value:
        return

    from sgpt.role import SystemRole

    SystemRole.create(value)


def show_role_callback(value: str | None) -> None:
    if not value:
        return

    from sgpt.role import SystemRole

    SystemRole.show(value)


def list_roles_callback(value: bool) -> None:
    if not value:
        return

    from sgpt.role import SystemRole

    SystemRole.list(value)


def install_functions_callback(value: bool) -> None:
    if not value:
        return

    from sgpt.llm_functions.init_functions import install_functions

    install_functions(None, value)


def main(
    prompt: str = typer.Argument(
        "",
        show_default=False,
        help="The prompt to generate completions for.",
    ),
    model: str | None = typer.Option(
        None,
        help="Large language model to use.",
    ),
    temperature: float = typer.Option(
        0.0,
        min=0.0,
        max=2.0,
        help="Randomness of generated output.",
    ),
    top_p: float = typer.Option(
        1.0,
        min=0.0,
        max=1.0,
        help="Limits highest probable tokens (words).",
    ),
    md: bool | None = typer.Option(
        None,
        help="Prettify markdown output.",
    ),
    shell: bool = typer.Option(
        False,
        "--shell",
        "-s",
        help="Generate and execute shell commands.",
        rich_help_panel="Assistance Options",
    ),
    interaction: bool | None = typer.Option(
        None,
        help="Interactive mode for --shell option.",
        rich_help_panel="Assistance Options",
    ),
    describe_shell: bool = typer.Option(
        False,
        "--describe-shell",
        "-d",
        help="Describe a shell command.",
        rich_help_panel="Assistance Options",
    ),
    code: bool = typer.Option(
        False,
        "--code",
        "-c",
        help="Generate only code.",
        rich_help_panel="Assistance Options",
    ),
    functions: bool | None = typer.Option(
        None,
        help="Allow function calls.",
        rich_help_panel="Assistance Options",
    ),
    editor: bool = typer.Option(
        False,
        help="Open $EDITOR to provide a prompt.",
    ),
    cache: bool = typer.Option(
        True,
        help="Cache completion results.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version.",
        callback=get_sgpt_version,
    ),
    chat: str | None = typer.Option(
        None,
        help="Follow conversation with id, " 'use "temp" for quick session.',
        rich_help_panel="Chat Options",
    ),
    repl: str | None = typer.Option(
        None,
        help="Start a REPL (Read–eval–print loop) session.",
        rich_help_panel="Chat Options",
    ),
    show_chat: str | None = typer.Option(
        None,
        help="Show all messages from provided chat id.",
        rich_help_panel="Chat Options",
    ),
    list_chats: bool = typer.Option(
        False,
        "--list-chats",
        "-lc",
        help="List all existing chat ids.",
        callback=list_chats_callback,
        rich_help_panel="Chat Options",
    ),
    role: str | None = typer.Option(
        None,
        help="System role for GPT model.",
        rich_help_panel="Role Options",
    ),
    create_role: str | None = typer.Option(
        None,
        help="Create role.",
        callback=create_role_callback,
        rich_help_panel="Role Options",
    ),
    show_role: str | None = typer.Option(
        None,
        help="Show role.",
        callback=show_role_callback,
        rich_help_panel="Role Options",
    ),
    list_roles: bool = typer.Option(
        False,
        "--list-roles",
        "-lr",
        help="List roles.",
        callback=list_roles_callback,
        rich_help_panel="Role Options",
    ),
    install_integration: bool = typer.Option(
        False,
        help="Install shell integration (ZSH and Bash only)",
        callback=install_shell_integration,
        hidden=True,  # Hiding since should be used only once.
    ),
    install_functions: bool = typer.Option(
        False,
        help="Install default functions.",
        callback=install_functions_callback,
        hidden=True,  # Hiding since should be used only once.
    ),
) -> None:
    stdin_passed = not sys.stdin.isatty()

    if stdin_passed:
        stdin = ""
        # TODO: This is very hacky.
        # In some cases, we need to pass stdin along with inputs.
        # When we want part of stdin to be used as a init prompt,
        # but rest of the stdin to be used as a inputs. For example:
        # echo "hello\n__sgpt__eof__\nThis is input" | sgpt --repl temp
        # In this case, "hello" will be used as a init prompt, and
        # "This is input" will be used as "interactive" input to the REPL.
        # This is useful to test REPL with some initial context.
        for line in sys.stdin:
            if "__sgpt__eof__" in line:
                break
            stdin += line
        prompt = f"{stdin}\n\n{prompt}" if prompt else stdin
        try:
            # Switch to stdin for interactive input.
            if os.name == "posix":
                sys.stdin = open("/dev/tty", "r")
            elif os.name == "nt":
                sys.stdin = open("CON", "r")
        except OSError:
            # Non-interactive shell.
            pass

    from sgpt.config import cfg

    model_name = model or cfg.get("DEFAULT_MODEL")
    markdown = md if md is not None else cfg.get("PRETTIFY_MARKDOWN") == "true"
    shell_interaction = (
        interaction if interaction is not None else cfg.get("SHELL_INTERACTION") == "true"
    )
    use_functions = (
        functions if functions is not None else cfg.get("OPENAI_USE_FUNCTIONS") == "true"
    )

    if show_chat:
        from sgpt.handlers.chat_handler import ChatHandler

        ChatHandler.show_messages(show_chat, markdown)

    if sum((shell, describe_shell, code)) > 1:
        raise UsageError(
            "Only one of --shell, --describe-shell, and --code options can be used at a time."
        )

    if chat and repl:
        raise UsageError("--chat and --repl options cannot be used together.")

    if editor and stdin_passed:
        raise UsageError("--editor option cannot be used with stdin input.")

    if editor:
        prompt = get_edited_prompt()

    from sgpt.role import DefaultRoles, SystemRole

    role_class = (
        DefaultRoles.check_get(shell, describe_shell, code)
        if not role
        else SystemRole.get(role)
    )

    role_supports_functions = role_class.name not in (
        DefaultRoles.SHELL.value,
        DefaultRoles.CODE.value,
        DefaultRoles.DESCRIBE_SHELL.value,
    )
    function_schemas = None
    if use_functions and role_supports_functions:
        from sgpt.function import get_openai_schemas

        function_schemas = get_openai_schemas() or None

    if repl:
        import readline  # noqa: F401
        from sgpt.handlers.repl_handler import ReplHandler

        # Will be in infinite loop here until user exits with Ctrl+C.
        ReplHandler(repl, role_class, markdown).handle(
            init_prompt=prompt,
            model=model_name,
            temperature=temperature,
            top_p=top_p,
            caching=cache,
            functions=function_schemas,
        )

    if chat:
        from sgpt.handlers.chat_handler import ChatHandler

        full_completion = ChatHandler(chat, role_class, markdown).handle(
            prompt=prompt,
            model=model_name,
            temperature=temperature,
            top_p=top_p,
            caching=cache,
            functions=function_schemas,
        )
    else:
        from sgpt.handlers.default_handler import DefaultHandler

        full_completion = DefaultHandler(role_class, markdown).handle(
            prompt=prompt,
            model=model_name,
            temperature=temperature,
            top_p=top_p,
            caching=cache,
            functions=function_schemas,
        )

    if shell and shell_interaction:
        from prompt_toolkit import PromptSession
        from sgpt.handlers.default_handler import DefaultHandler

        session = PromptSession()
        while True:
            option = typer.prompt(
                text="[E]xecute, [M]odify, [D]escribe, [A]bort",
                type=Choice(("e", "m", "d", "a", "y"), case_sensitive=False),
                default="e"
                if cfg.get("DEFAULT_EXECUTE_SHELL_CMD") == "true"
                else "a",
                show_choices=False,
                show_default=False,
            )

            if option in ("e", "y"):
                # "y" option is for keeping compatibility with old version.
                run_command(full_completion)
            elif option == "m":
                full_completion = session.prompt("", default=full_completion)
                continue
            elif option == "d":
                DefaultHandler(DefaultRoles.DESCRIBE_SHELL.get_role(), markdown).handle(
                    full_completion,
                    model=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    caching=cache,
                    functions=function_schemas,
                )
                continue
            break


def entry_point() -> None:
    typer.run(main)


if __name__ == "__main__":
    entry_point()
