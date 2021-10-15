import os
import requests
from zipfile import BadZipFile, ZipFile
from pathlib import Path
from inspect import currentframe

def download(url):
    return requests.get(url).content

#Do not use for anything other than calling
#From the post-download in the template file
#See this function as a macro.
def unzip_handin():
    caller = currentframe().f_back
    try:
        local = caller.f_locals
        attachment = local['attachment']
        base = local['base']
        path = local['path']
        onlineTA = local['template'].onlineTA
        if attachment['mime_class'] == 'zip':
            unpacked = os.path.join(base, 'unpacked')
            os.mkdir(unpacked)
            try:
                with ZipFile(path, 'r') as zip_ref:
                    try:
                        zip_ref.extractall(unpacked)
                        # Run through onlineTA
                        if onlineTA is not None:
                            run_onlineTA(base, unpacked, onlineTA)
                    except NotADirectoryError:
                        print(f"Attempted to unzip into a non-directory: {local['name']}")
            except BadZipFile:
                print(f"Attached archive not a zip-file: {local['name']}")
    finally:
        del caller

def run_onlineTA(base, handin, url):
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
