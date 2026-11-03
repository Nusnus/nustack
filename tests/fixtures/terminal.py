"""A command's terminal output read as plain text, whatever colour Typer forced."""

from rich.text import Text


# Typer forces colour when GITHUB_ACTIONS is set, so in CI its output holds ANSI
# codes: https://github.com/fastapi/typer/blob/0.27.3/typer/rich_utils.py#L78-L80
def plain(output: str) -> str:
    return Text.from_ansi(output).plain
