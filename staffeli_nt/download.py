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

if __name__ == '__main__':
    path_template = sys.argv[1]
    path_destination = sys.argv[2]
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
    course = canvas.get_course(39055)

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
        attr = user.attributes
        uid  = str(attr['id'])

        # add to participant list
        participants.append(
            create_student(
                attr
            )
        )

        try:
            # download every attachment
            files = [s for s in submission.attachments]

            # tag entire handin
            uuid = sorted([a['uuid'] for a in files])
            uuid = '-'.join(uuid)
            try:
                handins[uuid]['students'].append(user.attributes)
            except KeyError:
                handins[uuid] = {
                    'files': files,
                    'students': [user.attributes]
                }
            print('UUID:', uuid)

        except AttributeError:
            # empty handin
            empty_handins.append(user.attributes)

    # create submissions directory structure
    home = path_destination
    meta = os.path.join(home, 'meta.yml')
    empty = os.path.join(home, 'empty.yml')
    os.mkdir(home)

    # fetch every handin
    print('Downloading attachments')
    for (uuid, handin) in handins.items():
        print('Download:', uuid)

        # create submission directory
        name = '-'.join([str(u['id']) for u in handin['students']])
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
            '__MACOSX'
        ]
        for pattern in junk:
            pattern = os.path.join(base, pattern)
            for path in glob.glob(pattern):
                shutil.rmtree(path)



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