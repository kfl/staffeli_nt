import os
import time
from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import requests


def download(url, retries=3, delay=1.0):
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
    for attempt in range(retries):
        try:
            return requests.get(url).content
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        ):
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


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
