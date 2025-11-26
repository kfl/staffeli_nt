"""Centralised console configuration for staffeli_nt.

This module provides a single Rich Console instance with consistent styling
and theming for all terminal output in the application.
"""

from rich.console import Console
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
