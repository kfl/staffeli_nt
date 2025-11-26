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
})

console = Console(theme=staffeli_theme)


def print_error(message: str) -> None:
    """Print an error message in red with bold 'Error:' prefix.

    Args:
        message: The error message to display
    """
    console.print(f'[error]Error:[/error] {message}')


def print_success(message: str) -> None:
    """Print a success message in green.

    Args:
        message: The success message to display
    """
    console.print(f'[success]{message}[/success]')


def print_warning(message: str) -> None:
    """Print a warning message in yellow.

    Args:
        message: The warning message to display
    """
    console.print(f'[warning]{message}[/warning]')


def print_info(message: str) -> None:
    """Print an informational message in cyan.

    Args:
        message: The info message to display
    """
    console.print(f'[info]{message}[/info]')
