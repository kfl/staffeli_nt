import argparse
import os
import tempfile

from canvasapi import Canvas  # type: ignore[import-untyped]

from . import console as con
from .util import download, write_file
from .vas import GradingSheet, load_gradingsheet, load_meta_or_exit, load_template_or_exit

NAME_SHEET = 'grade.yml'


def grade(submission, grade, feedback, dry_run=True):
    # bail if dry
    con.print_info(f'Submit: user_id={submission.user_id}, grade={grade}')

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
    except AttributeError as e:
        con.print_error(
            f'Unexpected Canvas API response structure\n'
            f'Student ID: {submission.user_id}\n'
            f'Missing field: submission_comments\n\n'
            f'Run with --debug for details'
        )
        con.print_debug(
            f'Missing attribute on submission object\n'
            f'Submission repr: {repr(submission)}\n'
            f'{con.format_exception_debug(e)}'
        )

    # upload feedback if new
    if duplicate:
        con.print_info(f'Feedback already uploaded for user_id: {submission.user_id}')

    if dry_run:
        con.print_info(f'Would set grade to {grade} for user_id: {submission.user_id}')
        return

    if not duplicate:
        con.print_info(f'Uploading new feedback: {submission.user_id}')
        with tempfile.TemporaryDirectory() as c_dir:
            f_path = os.path.join(c_dir, 'feedback.txt')
            with open(f_path, 'w') as f:
                f.write(feedback)
            submission.upload_comment(f_path)

    # set grade
    con.print_info(f'Setting grade to {grade} for user_id: {submission.user_id}')
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

    sheets: list[tuple[str, GradingSheet]] = []

    meta_file = os.path.join(path_submissions, 'meta.yml')

    meta = load_meta_or_exit(meta_file)
    tmpl = load_template_or_exit(path_template)

    # fetch every grading sheet
    error_files: list[str] = []
    for root, dirs, files in os.walk(path_submissions, followlinks=True):
        for name in files:
            if name != NAME_SHEET:
                continue

            path = os.path.join(root, name)
            if (result := load_gradingsheet(path)) is not None:
                sheets.append(result)
            else:
                error_files.append(path)

    # Abort if there are errors in grade sheets
    if error_files:
        con.print_error(
            f"""Cannot proceed - {len(error_files)} grade sheet(s) have errors.

Files with errors:"""
        )
        for error_file in error_files:
            con.print(f'  [error]✗[/error] {error_file}')
        con.print_error(
            """
Please fix the errors above and try again.
Run with --debug for detailed error information."""
        )
        exit(1)

    # check that every sheet is complete
    graded = True
    for path, sheet in sheets:
        if not sheet.is_graded(tmpl):
            con.print_warning(f'Sheet not graded: {path}')
            graded = False

    if graded is False:
        con.print_warning('Grading is not complete')

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
        con.print_info(f'Prepare upload for section {section}')

    if live:
        con.print(f'[info]Uploading feedback for assignment:[/info] {assignment.name}')
        if not con.ask_confirm('Upload feedback for this assignment?'):
            return
    else:
        con.print_info('Doing a dry-run...')

    for stud_id, sheet in handins.items():
        submission = assignment.get_submission(stud_id, include=['submission_comments'])

        # total score
        total = sheet.get_grade(tmpl)
        if total is None and live:
            continue

        grade(submission, total, tmpl.format_md(sheet), dry_run=not live)

        if step:
            con.print(f'[info]Feedback for {stud_id}:[/info]')
            con.print(tmpl.format_md(sheet))
            con.print('-----------------------------------\n')
            input()
            con.print('\n' * 2)

    if write_local:
        con.print_info('Writing local feedback files')
        for path, sheet in sheets:
            f_path = path.replace('grade.yml', 'feedback.txt')
            con.print(f'[info]Writing to:[/info] {f_path}')
            write_file(f_path, tmpl.format_md(sheet), 'feedback file')

    if warn_missing:
        con.print('\n[info]Checking if some students are missing grades...[/info]')
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
                con.print(f'  Submission for {name} ({submission.user_id}) {group}: {state}')
                all_graded = False

        if all_graded:
            con.print_success('Looks good')
        else:
            con.print_warning('Still work to be done')
