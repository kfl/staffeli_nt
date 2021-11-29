import os
import requests
from zipfile import BadZipFile, ZipFile
from pathlib import Path

def download(url):
    return requests.get(url).content

def run_onlineTA(base, handin, url):
    path = sorted(Path(handin).rglob('README*'))
    if path:
        code_base = os.path.dirname(sorted(Path(handin).rglob('README*'))[0])
        with ZipFile('code.zip', 'w') as zf:
            for dirname, subdirs, files in os.walk(code_base):
                for f in files:
                    f_path=os.path.join(dirname, f)
                    zf.write(f_path,
                            os.path.relpath(f_path,code_base))
        req = requests.post(url,
                            files={'handin':
                                (zf.filename, open(zf.filename, 'rb'))})
        with open(os.path.join(base,'onlineTA_results.txt'), 'a') as f:
            f.writelines(req.text)
        os.remove('code.zip')
