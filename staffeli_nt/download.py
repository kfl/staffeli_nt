#!/usr/bin/env python3

import os
import sys
import glob
import shutil
import zipfile
import hashlib

from pathlib import Path

from vas import *
from util import *

def digest(data):
    return hashlib.sha256(data).digest()

def kuid(login_id):
    return login_id.split('@', maxsplit=1)[0]

if __name__ == '__main__':
    course_id = sys.argv[1]
    path_template = sys.argv[2]
    path_destination = sys.argv[3]
    path_token = os.path.join(
        str(Path.home()),
        '.canvas.token'
    )

    # sanity check

    with open(path_template, 'r') as f:
        template = parse_template(f.read())

    API_URL = 'https://absalon.ku.dk/'

    with open(path_token, 'r') as f:
        API_KEY = f.read().strip()


    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(course_id)

    assignments = sorted(
        list(course.get_assignments()),
        key=lambda x: x.name
    )

    for n, assignment in enumerate(assignments):
        print('%2d :' % n, assignment.name)

    index = int(input('Which assignment: '))

    assignment = assignments[index]
    print('Fetching:', assignment)


    handins = {}
    participants = []
    empty_handins = []
    submissions = assignment.get_submissions()

    for i, submission in enumerate(submissions):
        user = course.get_user(submission.user_id)
        # add to participant list
        participants.append(
            create_student(
                user
            )
        )

        if hasattr(submission, 'attachments'):
            print(f'User {user.name} handed in something')
            # collect which attachments to download
            files = [s for s in submission.attachments]

            # tag entire handin
            uuid = sorted([a['uuid'] for a in files])
            uuid = '-'.join(uuid)
            try:
                handins[uuid]['students'].append(user)
            except KeyError:
                handins[uuid] = {
                    'files': files,
                    'students': [user]
                }
#            print(f'Handin from {user.name} UUID: {uuid}')

        else:
            # empty handin
            empty_handins.append(user)

    # create submissions directory structure
    home = path_destination
    meta = os.path.join(home, 'meta.yml')
    empty = os.path.join(home, 'empty.yml')
    os.mkdir(home)

    # fetch every handin
    print('Downloading submissions')
    for (uuid, handin) in handins.items():
        student_names = ', '.join([u.name for u in handin['students']])
        print(f'Downloading submission from: {student_names}')

        # create submission directory
        name = '-'.join([kuid(u.login_id) for u in handin['students']])
        base = os.path.join(home, name)
        os.mkdir(base)

        # download submission
        for attachment in handin['files']:
            # download attachment
            path = os.path.join(base, attachment['filename'])
            data = download(attachment['url'])
            with open(path, 'wb') as f:
                f.write(data)

            # unzip attachments
            if attachment['mime_class'] == 'zip':
                with zipfile.ZipFile(path, 'r') as zip_ref:
                    zip_ref.extractall(base)

        # remove junk from submission directory
        junk = [
            '.git',
            '__MACOSX',
            '.stack-work',
            '.DS_Store'
        ]
        base_path = Path(base)
        for pattern in junk:
            for path in base_path.rglob(pattern):
                try:
                    shutil.rmtree(path)
                except NotADirectoryError:
                    os.remove(path)



        # create grading sheet from template
        grade = os.path.join(base, 'grade.yml')
        sheet = create_sheet(template, handin['students'])
        with open(grade, 'w') as f:
            yaml.dump(sheet.serialize(), f)


    # create a list of students with empty handins
    with open(empty, 'w') as f:
        yaml.dump(
            [create_student(p).serialize() for p in empty_handins],
            f
        )

    # create meta file
    with open(meta, 'w') as f:
        meta = Meta(
            course=MetaCourse(course.id, course.name),
            assignment=MetaAssignment(assignment.id, assignment.name)
        )
        yaml.dump(meta.serialize(), f)
