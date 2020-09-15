#!/usr/bin/env python3

import os
import sys
import tempfile

from os import access, R_OK
from os.path import isfile


from pathlib import Path

from vas import *
from util import *

NAME_SHEET = 'grade.yml'

def grade(submission, grade, path_feedback, dry_run=True):
    # bail if dry
    print(f'Submit: user_id={submission.user_id}, grade={grade}')
    if dry_run:
        return

    print(f'Uploading new feedback for user_id: {submission.user_id}')
    submission.upload_comment(path_feedback)

    # set grade
    print(f'Setting grade for user_id: {submission.user_id}')
    submission.edit(submission={'posted_grade': grade})

    # check if feedback is already uploaded
    # duplicate = False
    # for comment in submission.submission_comments:
    #     try:
    #         attachments = comment['attachments']
    #     except KeyError:
    #         attachments = []

    #     print('Comment with:', len(attachments), 'attachments')
    #     for attachment in attachments:
    #         if duplicate:
    #             break

    #         try:
    #             contents = download(attachment['url']).decode('utf-8')
    #         except UnicodeDecodeError:
    #             contents = ''

    #         duplicate = duplicate or contents.strip() == feedback.strip()

    # # upload feedback if new
    # if duplicate:
    #     print('Feedback already uploaded:', submission.user_id)

    # else:

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: upload_single <POINTS> <meta.yml> <grade.yml> <feedback.txt> [--live]")
        exit(1)

    points = sys.argv[1]
    path_meta_yml = sys.argv[2]
    path_grade_yml = sys.argv[3]
    path_feedback = sys.argv[4]

    live = '--live' in sys.argv

    path_token = os.path.join(
        str(Path.home()),
        '.canvas.token'
    )

    with open(path_meta_yml, 'r') as f:
        meta = parse_meta(f.read())

    with open(path_token, 'r') as f:
        API_KEY = f.read().strip()

    # get grade.yml
    with open(path_grade_yml, 'r') as f:
        sheet =  parse_sheet(f.read())

    if not(isfile(path_feedback) and access(path_feedback, R_OK)):
        print(f"File {path_feedback} doesn't exist or isn't readable")
        exit(1)

    # obtain canvas session
    API_URL = 'https://absalon.ku.dk/'

    canvas = Canvas(API_URL, API_KEY)
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

        grade(
            submission,
            total,
            path_feedback,
            dry_run = not live
        )
