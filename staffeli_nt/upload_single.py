
import argparse
from os import R_OK, access
from os.path import isfile

from .util import *
from .vas import *

NAME_SHEET = 'grade.yml'


def grade(submission, grade, path_feedback, dry_run=True):
    # bail if dry
    if dry_run:
        print(f'Would set grade to {grade} for user_id: {submission.user_id}')
        return

    print(f'Uploading new feedback for user_id: {submission.user_id}')
    submission.upload_comment(path_feedback)

    # set grade
    print(f'Setting grade to {grade} for user_id: {submission.user_id}')
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

    with open(path_meta_yml, 'r') as f:
        meta = parse_meta(f.read())

    # get grade.yml
    with open(path_grade_yml, 'r') as f:
        sheet = parse_sheet(f.read())

    if not (isfile(path_feedback) and access(path_feedback, R_OK)):
        print(f"File {path_feedback} doesn't exist or isn't readable")
        exit(1)

    canvas = Canvas(api_url, api_key)
    course = canvas.get_course(meta.course.id)
    assignment = course.get_assignment(meta.assignment.id)

    if live:
        print('Uploading feedback to:', assignment)
        choice = input('Sure? (y/n) : ')
        assert choice.strip() == 'y'
    else:
        print('Doing a dry-run...')

    for student in sheet.students:
        submission = assignment.get_submission(student.id)
        total = points

        grade(submission, total, path_feedback, dry_run=not live)
