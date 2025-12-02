#!/usr/bin/env python3


import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from staffeli_nt import download, info, scan, upload, upload_single
from staffeli_nt.console import print_error, set_debug_mode


def get_version() -> str:
    """Get version from package metadata.

    Returns:
        Version string or 'development' if not installed.
    """
    try:
        return version('staffeli-nt')
    except PackageNotFoundError:
        return 'development'


def get_token_path(custom_path: Optional[str] = None) -> Path:
    """Get the Canvas token file path.

    Args:
        custom_path: Optional custom path to token file

    Returns:
        Path object for the token file
    """
    if custom_path:
        return Path(custom_path)
    return Path.home() / '.canvas.token'


def main() -> None:
    # Create parser and add global flags with version in description
    version_str = get_version()
    parser = argparse.ArgumentParser(
        prog='staffeli',
        description=f'Staffeli NT - Canvas LMS command-line tool (version {version_str})',
        epilog='For more information, visit https://github.com/kfl/staffeli_nt',
    )
    parser.add_argument('--version', action='version', version=version_str)
    parser.add_argument(
        '--token',
        type=str,
        metavar='PATH',
        help='path to Canvas token file (default: ~/.canvas.token)',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='show detailed error information and stack traces',
    )

    # Add all subparsers
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand')
    scan.add_subparser(subparsers)
    download.add_subparser(subparsers)
    info.add_subparser(subparsers)
    upload.add_subparser(subparsers)
    upload_single.add_subparser(subparsers)

    # Parse arguments (--help and --version work here!)
    args = parser.parse_args()

    # Set debug mode globally (checked only in console.py)
    set_debug_mode(args.debug)

    # Check if subcommand was provided
    if not hasattr(args, 'main'):
        parser.print_help()
        return

    # NOW check authentication (only for actual subcommands)
    path_token = get_token_path(args.token)
    if not path_token.exists():
        print_error(f'Missing Canvas token at {path_token}')
        sys.exit(1)

    api_url = 'https://absalon.ku.dk/'
    api_key = path_token.read_text().strip()

    # Execute subcommand
    args.main(api_url, api_key, args)


if __name__ == '__main__':
    main()
