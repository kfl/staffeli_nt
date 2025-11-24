import os
import argparse

from .vas import *

NAME_SHEET = 'grade.yml'

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
LIGHT_PURPLE = '\033[94m'
PURPLE = '\033[95m'
END = '\033[0m'


def add_subparser(subparsers: argparse._SubParsersAction):
    parser: argparse.ArgumentParser = subparsers.add_parser(
        name='scan', help='check if grading is fully done'
    )
    parser.add_argument(
        'path_template', type=str, metavar='TEMPLATE_PATH', help='path to the YAML template'
    )
    parser.add_argument(
        'path_submissions', type=str, metavar='SUBMISSIONS_PATH', help='path to submissions folder'
    )
    parser.set_defaults(main=main)


def main(api_url, api_key, args: argparse.Namespace):
    path_template = args.path_template
    path_submissions = args.path_submissions

    sheets = []

    with open(path_template, 'r') as f:
        tmpl = parse_template(f.read())

    # fetch every grading sheet
    for root, dirs, files in os.walk(path_submissions):
        for name in files:
            if name != NAME_SHEET:
                continue

            path = os.path.join(root, name)
            # print(path)
            with open(path, 'r') as f:
                sheets.append((path, parse_sheet(f.read())))

    # check that every sheet is complete
    graded = True
    missing = 0
    done = 0
    for path, sheet in sheets:
        if not sheet.is_graded(tmpl):
            print(f'{RED}█{END} {path} is not graded')
            graded = False
            missing += 1
        else:
            total = sheet.get_grade(tmpl)
            tp = tmpl.total_points
            print(f'{GREEN}█{END} {total}/{tp} points for {path}')
            done += 1

    if graded is False:
        print(f'Grading is not complete, {done} done, {missing} missing')
    else:
        print('Yay, time to upload')
