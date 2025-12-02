"""Centralised console configuration for staffeli_nt.

This module provides a single Rich Console instance with consistent styling
and theming for all terminal output in the application.
"""

from collections.abc import Iterable
from typing import TypeVar

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm, IntPrompt
from rich.theme import Theme

# Custom theme with semantic colour names
staffeli_theme = Theme(
    {
        'info': 'cyan',
        'success': 'green',
        'warning': 'yellow',
        'error': 'red bold',
        'highlight': 'magenta',
        'progress': 'blue',
        'muted': 'dim',
        'debug': 'blue dim',
        'verbose': 'dim',
        'menu': 'bright_cyan bold',
    }
)

console = Console(theme=staffeli_theme, highlight=False)


def print(*args, **kwargs):
    """General printing. Wrapper for console.print().
    """
    console.print(*args, **kwargs)


# Global debug state - controlled via set_debug_mode()
_debug_enabled = False


def set_debug_mode(enabled: bool) -> None:
    global _debug_enabled
    _debug_enabled = enabled


def print_error(message: str) -> None:
    """Print an error message in red with bold 'Error:' prefix.

    Multi-line messages are automatically indented for readability.

    Args:
        message: The error message to display
    """
    lines = message.split('\n')
    if len(lines) == 1:
        console.print(f'[error]Error:[/error] {message}')
    else:
        console.print(f'[error]Error:[/error] {lines[0]}')
        for line in lines[1:]:
            console.print(f'       {line}')


def print_success(message: str) -> None:
    """Print a success message in green.

    Multi-line messages are automatically indented for readability.

    Args:
        message: The success message to display
    """
    lines = message.split('\n')
    console.print(f'[success]{lines[0]}[/success]')
    for line in lines[1:]:
        console.print(f'  {line}')


def print_warning(message: str) -> None:
    """Print a warning message in yellow.

    Multi-line messages are automatically indented for readability.

    Args:
        message: The warning message to display
    """
    lines = message.split('\n')
    console.print(f'[warning]{lines[0]}[/warning]')
    for line in lines[1:]:
        console.print(f'  {line}')


def print_info(message: str) -> None:
    """Print an informational message in cyan.

    Multi-line messages are automatically indented for readability.

    Args:
        message: The info message to display
    """
    lines = message.split('\n')
    console.print(f'[info]{lines[0]}[/info]')
    for line in lines[1:]:
        console.print(f'  {line}')


def print_debug(message: str) -> None:
    """Print a debug message in blue dim with [DEBUG] prefix.

    Only prints if debug mode is enabled via set_debug_mode().
    Multi-line messages are automatically indented for readability.

    Args:
        message: The debug message to display
    """
    if not _debug_enabled:
        return

    lines = message.split('\n')
    console.print(f'[debug][DEBUG][/debug] {lines[0]}')
    for line in lines[1:]:
        console.print(f'        {line}')


def print_verbose(message: str) -> None:
    """Print a verbose message in dim.

    Multi-line messages are automatically indented for readability.

    Args:
        message: The verbose message to display
    """
    lines = message.split('\n')
    console.print(f'[verbose]{lines[0]}[/verbose]')
    for line in lines[1:]:
        console.print(f'  {line}')


def format_exception_debug(e: Exception, include_trace: bool = True) -> str:
    """Format exception details for debug output.

    Includes exception type, message, cause chain, and optional stack trace.

    Args:
        e: The exception to format
        include_trace: Whether to include stack trace (default: True)

    Returns:
        Formatted string with exception details
    """
    import traceback

    lines = []
    lines.append(f'Exception type: {type(e).__name__}')
    lines.append(f'Exception message: {str(e)}')

    # Walk the exception chain
    if e.__cause__ or e.__context__:
        lines.append('')
        lines.append('Exception chain:')
        current = e.__cause__ if e.__cause__ else e.__context__
        depth = 1
        while current:
            lines.append(f'  {"  " * depth}Caused by: {type(current).__name__}: {str(current)}')
            current = current.__cause__ if current.__cause__ else current.__context__
            depth += 1

    # Stack trace (last 10 frames to keep manageable)
    if include_trace:
        lines.append('')
        lines.append('Stack trace:')
        tb_lines = traceback.format_tb(e.__traceback__)
        for tb_line in tb_lines[-10:]:
            for line in tb_line.strip().split('\n'):
                lines.append(f'  {line}')

    return '\n'.join(lines)


T = TypeVar('T')


def with_progress(description: str, iterable: Iterable[T], total: int) -> Iterable[T]:
    """Wrap an iterable with a progress bar.

    Args:
        description: Description to show in progress bar
        iterable: The iterable to wrap (e.g., executor.map() result)
        total: Total number of items expected

    Yields:
        Items from the iterable, while updating progress bar
    """
    with Progress(
        SpinnerColumn(),
        TextColumn('[progress.description]{task.description}'),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(description, total=total)
        for item in iterable:
            yield item
            progress.update(task, advance=1)


def create_shared_progress() -> Progress:
    """Create a Progress instance that can be shared across threads.

    Returns:
        A Progress instance configured for multi-threaded file downloads
    """
    return Progress(
        SpinnerColumn(),
        TextColumn('[progress.description]{task.description}'),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=True,  # Expand to fill available space
        refresh_per_second=10,  # Update display frequently
    )


def ask_menu(prompt: str, options: list, default: int | None = None) -> int:
    """Display a menu and prompt for selection.

    Args:
        prompt: The prompt message to display (e.g., "Select assignment")
        options: List of options to display (will be converted to strings)
        default: Optional default index (0-based)

    Returns:
        The index of the selected option (0-based)
    """
    console.print(f'\n[info]{prompt}:[/info]')
    for n, option in enumerate(options):
        console.print(f'[menu]{n:2d}[/menu] : {option}')

    while True:
        if default is not None:
            result = IntPrompt.ask('Select', console=console, default=default)
        else:
            result = IntPrompt.ask('Select', console=console)
        if 0 <= result < len(options):
            return result
        print_error(f'Please enter a number between 0 and {len(options) - 1}')


def ask_confirm(prompt: str, default: bool = False) -> bool:
    """Ask for yes/no confirmation.

    Args:
        prompt: The question to ask
        default: Default answer if user just presses Enter

    Returns:
        True if user confirms, False otherwise
    """
    return Confirm.ask(f'[warning]{prompt}[/warning]', console=console, default=default)
