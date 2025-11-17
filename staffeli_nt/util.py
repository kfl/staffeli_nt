import os
import requests
from zipfile import ZipFile
from pathlib import Path


def download(url):
    return requests.get(url).content


def run_onlineTA(base, handin, url):
    path = sorted(Path(handin).rglob('README*'))
    if path:
        code_base = os.path.dirname(sorted(Path(handin).rglob('README*'))[0])
        zip_filename = 'code.zip'
        with ZipFile(zip_filename, 'w') as zf:
            for dirname, subdirs, files in os.walk(code_base):
                for f in files:
                    f_path = os.path.join(dirname, f)
                    zf.write(f_path,
                             os.path.relpath(f_path, code_base))

        # Open and post the zip file after it's been closed
        with open(zip_filename, 'rb') as zip_file:
            req = requests.post(url,
                                files={'handin': (zip_filename, zip_file)})

        with open(os.path.join(base, 'onlineTA_results.txt'), 'a') as res:
            res.writelines(req.text)

        os.remove(zip_filename)
