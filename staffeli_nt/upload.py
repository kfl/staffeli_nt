#!/usr/bin/env python3

import os
import sys
import tempfile

from pathlib import Path
from ruamel.yaml import YAMLError
from vas import *
from util import *

NAME_SHEET = 'grade.yml'

def grade(submission, grade, feedback, dry_run=True):
    # bail if dry
    print('Submit: user_id=%d, grade=%s' % (submission.user_id, grade))

    # check if feedback is already uploaded
    duplicate = False
    try:
        for comment in submission.submission_comments:
            try:
                attachments = comment['attachments']
            except KeyError:
                attachments = []

            #print('Comment with:', len(attachments), 'attachments')
            for attachment in attachments:
                if duplicate:
                    break

                try:
                    contents = download(attachment['url']).decode('utf-8')
                except UnicodeDecodeError:
                    contents = ''

                duplicate = duplicate or contents.strip() == feedback.strip()
    except AttributeError:
        print("Internal problem?: It seems that the submission don't have a submission_comments field")
        print("   ", repr(submission))

    # upload feedback if new
    if duplicate:
        print(f'Feedback already uploaded for user_id: {submission.user_id}')

    if dry_run:
        print(f'Would set grade to {grade} for user_id: {submission.user_id}')
        return

    if not duplicate:
        print('Uploading new feedback:', submission.user_id)
        with tempfile.TemporaryDirectory() as c_dir:
            f_path = os.path.join(c_dir, 'feedback.txt')
            with open(f_path, 'w') as f:
                f.write(feedback)
            submission.upload_comment(f_path)

    # set grade
    print(f'Setting grade to {grade} for user_id: {submission.user_id}')
    submission.edit(submission={'posted_grade': grade})



if __name__ == '__main__':

    path_template = sys.argv[1]
    path_submissions = sys.argv[2]
    live = '--live' in sys.argv
    step = '--step' in sys.argv
    warn_missing = '--warn-missing' in sys.argv
    write_local = '--write-local' in sys.argv and not live

    sheets = []

    path_token = os.path.join(
        str(Path.home()),
        '.canvas.token'
    )

    meta_file = os.path.join(
        path_submissions,
        'meta.yml'
    )

    with open(meta_file, 'r') as f:
        meta = parse_meta(f.read())

    with open(path_template, 'r') as f:
        tmpl = parse_template(f.read())

    with open(path_token, 'r') as f:
        API_KEY = f.read().strip()

    # fetch every grading sheet
    error_files = []
    for root, dirs, files in os.walk(path_submissions, followlinks=True):
        for name in files:
            if name != NAME_SHEET:
                continue

            path = os.path.join(root, name)
            with open(path, 'r') as f:
                try:
                    sheets.append((
                        path,
                        parse_sheet(f.read())
                    ))
                except YAMLError as exc:
                    print(f"\nFailed to parse {path}:")
                    print(f"  {exc}\n")
                    error_files.append(path)
                except Exception as exc:
                    print(f"Some error in {path}. Error description: {exc}")
                    error_files.append(path)

    # Aborts if there are syntax errors in the .yml files, and prints offenders
    if error_files:
        print ("There were errors in the following files:")
        print (*error_files, sep="\n")
        exit()

    # check that every sheet is complete
    graded = True
    for (path, sheet) in sheets:
        if not sheet.is_graded(tmpl):
            print('Sheet not graded:', path)
            graded = False

    if graded is False:
        print('Grading is not complete')


    # construct reverse map[user] -> grading sheet
    handins = {}
    for (_, sheet) in sheets:
        for student in sheet.students:
            assert student.id not in handins, 'student assigned multiple sheets'
            handins[student.id] = sheet

    # obtain canvas session
    API_URL = 'https://absalon.ku.dk/'

    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(meta.course.id)
    assignment = course.get_assignment(meta.assignment.id)
    submissions = []
    section = None

    if meta.assignment.section is not None:
        section = course.get_section(meta.assignment.section,
                                     include=['students', 'enrollments'])
        print(f'Prepare upload for section {section}')

    if live:
        print(f'Uploading feedback for assignment: {assignment.name}')
        choice = input('Sure? (y/n) : ')
        assert choice.strip() == 'y'
    else:
        print('Doing a dry-run...')

    for stud_id, sheet in handins.items():
        submission = assignment.get_submission(stud_id, include=['submission_comments'])

        # total score
        total = sheet.get_grade(tmpl)
        if total is None and live:
            continue

        grade(
            submission,
            total,
            tmpl.format_md(sheet),
            dry_run = not live
        )

        if step:
            print(f'Feedback for {stud_id}: ')
            print(tmpl.format_md(sheet))
            print('-----------------------------------\n')
            input()
            print('\n'*2)

    if write_local:
        print('Writing local')
        for (path, sheet) in sheets:
            f_path = path.replace('grade.yml', 'feedback.txt')
            print('writing to: ', f_path)
            with open(f_path, 'w') as f:
                f.write(tmpl.format_md(sheet))



    if warn_missing:
        print('\nChecking if some students are missing grades...')
        all_graded = True

        if section:
            s_ids = [s['id'] for s in section.students if all([ e['enrollment_state'] == 'active'
                                                                for e in s['enrollments']])]
            submissions = section.get_multiple_submissions(assignment_ids=[assignment.id],
                                                           student_ids=s_ids,
                                                           include=['user','group'])
        else:
            submissions = assignment.get_submissions(include=['user','group'])


        for submission in submissions:
            if submission.workflow_state in ('submitted', 'pending_review'):
                name = submission.user["short_name"]
                group = ''.join(f'({g})' for g in [submission.group.get("name")] if g)
                print(f'  Submission for {name} ({submission.user_id}) {group}: {submission.workflow_state}')
                all_graded = False

        if all_graded:
            print("Looks good")
        else:
            print("Still work to be done")
