import collections
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar
from zipfile import ZipFile

import requests
from ruamel.yaml import YAML

from .console import format_exception_debug, print_debug, print_error

T = TypeVar('T')


def create_yaml():
    """Create a new YAML instance with standard configuration.

    The ruamel.yaml library is not thread-safe, so each thread should
    create its own YAML instance when running in parallel.
    """
    y = YAML()
    y.indent(mapping=4, sequence=2, offset=2)
    y.Representer.add_representer(collections.OrderedDict, y.Representer.represent_dict)
    return y


def dump_yaml(
    path: str,
    data: Any,
    file_description: str = 'YAML file',
    exit_on_error: bool = False,
) -> bool:
    """Dump data to YAML file with proper error handling.

    Args:
        path: Path where file should be written
        data: Data to dump (dict, list, or any YAML-serializable type)
        file_description: Human-readable description for error messages
        exit_on_error: If True, exit on error; if False, return False on error

    Returns:
        True on success, False on failure (unless exit_on_error=True)
    """
    try:
        yaml_instance = create_yaml()
        with open(path, 'w') as f:
            yaml_instance.dump(data, f)
        return True
    except OSError as e:
        print_error(f'Failed to write {file_description}: {path}\n\nRun with --debug for details')
        print_debug(format_exception_debug(e))
        if exit_on_error:
            sys.exit(1)
        return False


def download(url, retries=3, delay=1.0) -> bytes:
    """Download a file from a URL with retry logic for transient failures.

    Args:
        url: The URL to download from
        retries: Number of retry attempts for transient errors
        delay: Delay in seconds between retries

    Returns:
        The downloaded content as bytes

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception = None
    for attempt in range(retries):
        try:
            return requests.get(url).content
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        ) as e:
            last_exception = e
            if attempt < retries - 1:
                time.sleep(delay)

    # If we get here, all retries failed
    if last_exception:
        raise last_exception
    raise RuntimeError(f'Failed to download {url} after {retries} retries')


def download_streaming(
    url: str,
    retries: int = 3,
    delay: float = 1.0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bytes:
    """Download a file with streaming and progress reporting.

    Args:
        url: The URL to download from
        retries: Number of retry attempts for transient errors
        delay: Delay in seconds between retries
        progress_callback: Optional callback(current_bytes, total_bytes) for progress updates

    Returns:
        The downloaded content as bytes

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception = None
    for attempt in range(retries):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # Get total size from headers if available
            total_size = int(response.headers.get('content-length', 0))

            if progress_callback and total_size > 0:
                progress_callback(0, total_size)

            # Download in chunks
            chunks = []
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive chunks
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

            return b''.join(chunks)

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        ) as e:
            last_exception = e
            if attempt < retries - 1:
                time.sleep(delay)

    # If we get here, all retries failed
    if last_exception:
        raise last_exception
    raise RuntimeError(f'Failed to download {url} after {retries} retries')


def run_onlineTA(base, handin, url):
    path = sorted(Path(handin).rglob('README*'))
    if path:
        code_base = os.path.dirname(sorted(Path(handin).rglob('README*'))[0])
        zip_filename = 'code.zip'
        with ZipFile(zip_filename, 'w') as zf:
            for dirname, subdirs, files in os.walk(code_base):
                for f in files:
                    f_path = os.path.join(dirname, f)
                    zf.write(f_path, os.path.relpath(f_path, code_base))

        # Open and post the zip file after it's been closed
        with open(zip_filename, 'rb') as zip_file:
            req = requests.post(url, files={'handin': (zip_filename, zip_file)})

        with open(os.path.join(base, 'onlineTA_results.txt'), 'a') as res:
            res.writelines(req.text)

        os.remove(zip_filename)


def load_and_parse_yaml(
    path: str,
    parser: Callable[[str], T],
    file_type: str,
) -> T | None:
    """Load and parse YAML file, returning None on error.

    Args:
        path: Path to YAML file
        parser: Function to parse file content (e.g., parse_meta, parse_template)
        file_type: Description of file type (e.g., "meta.yml", "template")

    Returns:
        Parsed object on success, None on failure
    """
    try:
        with open(path, 'r') as f:
            content = f.read()
        return parser(content)
    except FileNotFoundError as e:
        print_error(f'{file_type} file not found: {path}')
        print_debug(format_exception_debug(e))
        return None
    except Exception as e:
        print_error(f'Failed to parse {file_type} file: {path}\n\nRun with --debug for details')
        print_debug(format_exception_debug(e))
        return None


def write_file(
    path: str,
    content: str | bytes,
    file_description: str = 'file',
) -> None:
    """Write content to file with proper error handling.

    Args:
        path: Path where file should be written
        content: String or bytes to write
        file_description: Human-readable description for error messages

    Exits with error message on failure.
    """
    try:
        mode = 'wb' if isinstance(content, bytes) else 'w'
        encoding = None if isinstance(content, bytes) else 'utf-8'
        with open(path, mode, encoding=encoding) as f:
            f.write(content)
    except (PermissionError, OSError) as e:
        print_error(f'Failed to write {file_description}: {path}\n\nRun with --debug for details')
        print_debug(format_exception_debug(e))
        sys.exit(1)
