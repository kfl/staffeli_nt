import os
import time
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
