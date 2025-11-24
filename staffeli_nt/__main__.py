#!/usr/bin/env python3


import argparse
import os
import sys
from pathlib import Path

from staffeli_nt import download, info, scan, upload, upload_single


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand')
    scan.add_subparser(subparsers)
    download.add_subparser(subparsers)
    info.add_subparser(subparsers)
    upload.add_subparser(subparsers)
    upload_single.add_subparser(subparsers)

    path_token = os.path.join(str(Path.home()), '.canvas.token')

    if not os.path.exists(path_token):
        print(f'Error: Missing Canvas token at {path_token}.')
        sys.exit(0)

    api_url = 'https://absalon.ku.dk/'

    with open(path_token, 'r') as f:
        api_key = f.read().strip()

    args = parser.parse_args()
    if not hasattr(args, 'main'):
        parser.print_help()
        return

    args.main(api_url, api_key, args)


if __name__ == '__main__':
    main()
