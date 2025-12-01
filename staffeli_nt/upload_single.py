import argparse
import sys
from os import R_OK, access
from os.path import isfile

from canvasapi import Canvas  # type: ignore[import-untyped]

from .console import ask_confirm, console, print_error, print_info
from .util import *
from .vas import *

NAME_SHEET = 'grade.yml'


def grade(submission, grade, path_feedback, dry_run=True):
    # bail if dry
    if dry_run:
        print_info(f'Would set grade to {grade} for user_id: {submission.user_id}')
        return

    print_info(f'Uploading new feedback for user_id: {submission.user_id}')
    submission.upload_comment(path_feedback)

    # set grade
    print_info(f'Setting grade to {grade} for user_id: {submission.user_id}')
    submission.edit(submission={'posted_grade': grade})


def add_subparser(subparsers: argparse._SubParsersAction):
    parser: argparse.ArgumentParser = subparsers.add_parser(
        name='upload-single', help='upload feedback for a single submission'
    )
    parser.add_argument('points', type=str, metavar='INT', help='number of points given')
    parser.add_argument(
        'path_meta_yml',
        type=str,
        metavar='META_PATH',
        help='YAML file containg meta data related to the submission',
    )
    parser.add_argument(
        'path_grade_yml', type=str, metavar='GRADE_PATH', help='YAML file containing the grade'
    )
    parser.add_argument(
        'path_feedback',
        type=str,
        metavar='FEEDBACK_PATH',
        help='the path to the text file containing feedback',
    )
    parser.add_argument('--live', action='store_true', help='upload feedback for submission')
    parser.set_defaults(main=main)


def main(api_url, api_key, args: argparse.Namespace):
    points = args.points
    path_meta_yml = args.path_meta_yml
    path_grade_yml = args.path_grade_yml
    path_feedback = args.path_feedback

    live = args.live

    meta = load_meta_or_exit(path_meta_yml)
    if (sheet := load_and_parse_yaml(path_grade_yml, parse_sheet, 'grade sheet')) is None:
        sys.exit(1)

    if not (isfile(path_feedback) and access(path_feedback, R_OK)):
        print_error(f"File {path_feedback} doesn't exist or isn't readable")
        exit(1)

    canvas = Canvas(api_url, api_key)
    course = canvas.get_course(meta.course.id)
    assignment = course.get_assignment(meta.assignment.id)

    if live:
        console.print(f'[info]Uploading feedback to:[/info] {assignment}')
        if not ask_confirm('Sure?'):
            return
    else:
        print_info('Doing a dry-run...')

    for student in sheet.students:
        submission = assignment.get_submission(student.id)
        total = points

        grade(submission, total, path_feedback, dry_run=not live)
