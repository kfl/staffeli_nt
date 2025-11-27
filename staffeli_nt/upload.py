import argparse
import os
import tempfile

from canvasapi import Canvas  # type: ignore[import-untyped]
from ruamel.yaml import YAMLError

from .console import (
    ask_confirm,
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from .util import *
from .vas import *

NAME_SHEET = 'grade.yml'


def grade(submission, grade, feedback, dry_run=True):
    # bail if dry
    print_info(f'Submit: user_id={submission.user_id}, grade={grade}')

    # check if feedback is already uploaded
    duplicate = False
    try:
        for comment in submission.submission_comments:
            try:
                attachments = comment.attachments
            except KeyError:
                attachments = []

            # print('Comment with:', len(attachments), 'attachments')
            for attachment in attachments:
                if duplicate:
                    break

                try:
                    contents = download(attachment.url).decode('utf-8')
                except UnicodeDecodeError:
                    contents = ''

                duplicate = duplicate or contents.strip() == feedback.strip()
    except AttributeError:
        print_error(
            "Internal problem?: It seems that the submission don't have a "
            'submission_comments field\n'
            f'{repr(submission)}'
        )

    # upload feedback if new
    if duplicate:
        print_info(f'Feedback already uploaded for user_id: {submission.user_id}')

    if dry_run:
        print_info(f'Would set grade to {grade} for user_id: {submission.user_id}')
        return

    if not duplicate:
        print_info(f'Uploading new feedback: {submission.user_id}')
        with tempfile.TemporaryDirectory() as c_dir:
            f_path = os.path.join(c_dir, 'feedback.txt')
            with open(f_path, 'w') as f:
                f.write(feedback)
            submission.upload_comment(f_path)

    # set grade
    print_info(f'Setting grade to {grade} for user_id: {submission.user_id}')
    submission.edit(submission={'posted_grade': grade})


def add_subparser(subparsers: argparse._SubParsersAction):
    parser: argparse.ArgumentParser = subparsers.add_parser(
        name='upload', help='upload feedback for submissions'
    )
    parser.add_argument(
        'path_template', type=str, metavar='TEMPLATE_PATH', help='path to the YAML template'
    )
    parser.add_argument(
        'path_submissions',
        type=str,
        metavar='SUBMISSIONS_PATH',
        help='destination to submissions folder',
    )
    parser.add_argument(
        '--live', action='store_true', help='upload all feedback for submissions in the directory'
    )
    parser.add_argument(
        '--step',
        action='store_true',
        help='to review all feedback for submissions in the directory',
    )
    parser.add_argument('--warn-missing', action='store_true', help='warn if grades are missing')
    parser.add_argument(
        '--write-local',
        action='store_true',
        help='writes the feedback locally unless --live is given',
    )
    parser.set_defaults(main=main)


def main(api_url, api_key, args: argparse.Namespace):
    path_template = args.path_template
    path_submissions = args.path_submissions
    live = args.live
    step = args.step
    warn_missing = args.warn_missing
    write_local = args.write_local and not live

    sheets = []

    meta_file = os.path.join(path_submissions, 'meta.yml')

    with open(meta_file, 'r') as f:
        meta = parse_meta(f.read())

    with open(path_template, 'r') as f:
        tmpl = parse_template(f.read())

    # fetch every grading sheet
    error_files = []
    for root, dirs, files in os.walk(path_submissions, followlinks=True):
        for name in files:
            if name != NAME_SHEET:
                continue

            path = os.path.join(root, name)
            with open(path, 'r') as f:
                try:
                    sheets.append((path, parse_sheet(f.read())))
                except YAMLError as exc:
                    print_error(f'Failed to parse {path}:\n{exc}')
                    error_files.append(path)
                except Exception as exc:
                    print_error(f'Some error in {path}. Error description: {exc}')
                    error_files.append(path)

    # Aborts if there are syntax errors in the .yml files, and prints offenders
    if error_files:
        print_error('There were errors in the following files:')
        for error_file in error_files:
            print_error(f'  {error_file}')
        exit(1)

    # check that every sheet is complete
    graded = True
    for path, sheet in sheets:
        if not sheet.is_graded(tmpl):
            print_warning(f'Sheet not graded: {path}')
            graded = False

    if graded is False:
        print_warning('Grading is not complete')

    # construct reverse map[user] -> grading sheet
    handins = {}
    for _, sheet in sheets:
        for student in sheet.students:
            assert student.id not in handins, 'student assigned multiple sheets'
            handins[student.id] = sheet

    canvas = Canvas(api_url, api_key)
    course = canvas.get_course(meta.course.id)
    assignment = course.get_assignment(meta.assignment.id)
    submissions = []
    section = None

    if meta.assignment.section is not None:
        section = course.get_section(meta.assignment.section, include=['students', 'enrollments'])
        print_info(f'Prepare upload for section {section}')

    if live:
        console.print(f'[info]Uploading feedback for assignment:[/info] {assignment.name}')
        if not ask_confirm('Upload feedback for this assignment?'):
            return
    else:
        print_info('Doing a dry-run...')

    for stud_id, sheet in handins.items():
        submission = assignment.get_submission(stud_id, include=['submission_comments'])

        # total score
        total = sheet.get_grade(tmpl)
        if total is None and live:
            continue

        grade(submission, total, tmpl.format_md(sheet), dry_run=not live)

        if step:
            console.print(f'[info]Feedback for {stud_id}:[/info]')
            console.print(tmpl.format_md(sheet))
            console.print('-----------------------------------\n')
            input()
            console.print('\n' * 2)

    if write_local:
        print_info('Writing local')
        for path, sheet in sheets:
            f_path = path.replace('grade.yml', 'feedback.txt')
            console.print(f'[info]Writing to:[/info] {f_path}')
            with open(f_path, 'w') as f:
                f.write(tmpl.format_md(sheet))

    if warn_missing:
        console.print('\n[info]Checking if some students are missing grades...[/info]')
        all_graded = True

        if section:
            s_ids = [
                s['id']
                for s in section.students
                if all([e['enrollment_state'] == 'active' for e in s['enrollments']])
            ]
            submissions = section.get_multiple_submissions(
                assignment_ids=[assignment.id], student_ids=s_ids, include=['user', 'group']
            )
        else:
            submissions = assignment.get_submissions(include=['user', 'group'])

        for submission in submissions:
            if submission.workflow_state in ('submitted', 'pending_review'):
                name = submission.user['short_name']
                group = ''.join(f'({g})' for g in [submission.group.get('name')] if g)
                state = submission.workflow_state
                console.print(f'  Submission for {name} ({submission.user_id}) {group}: {state}')
                all_graded = False

        if all_graded:
            print_success('Looks good')
        else:
            print_warning('Still work to be done')
