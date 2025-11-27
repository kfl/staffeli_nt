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
from rich.theme import Theme

# Custom theme with semantic colour names
staffeli_theme = Theme({
    'info': 'cyan',
    'success': 'green',
    'warning': 'yellow',
    'error': 'red bold',
    'highlight': 'magenta',
    'progress': 'blue',
    'muted': 'dim',
    'debug': 'blue dim',
    'verbose': 'dim',
})

console = Console(theme=staffeli_theme)


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

    Multi-line messages are automatically indented for readability.

    Args:
        message: The debug message to display
    """
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
