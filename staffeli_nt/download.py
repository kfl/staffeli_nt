#!/usr/bin/env python3

import os
import sys
import glob
import shutil
import zipfile
import hashlib
import re
from zipfile import BadZipFile, ZipFile
from pathlib import Path
import requests
from typing import Dict, Any


from vas import *
from util import *

def digest(data):
    return hashlib.sha256(data).digest()

def kuid(login_id):
    return login_id.split('@', maxsplit=1)[0]

def smart_key(name):
   parts = re.findall('[^0-9]+|[0-9]+', name)
   key = []
   for part in parts:
       try:
          key.append(format(int(part), '05'))
       except ValueError:
          key.append(part)
   return key

def sort_by_name(named):
    return sorted( list(named), key=lambda x: smart_key(x.name) )

def ta_file(args):
    for idx, arg in enumerate(args):
        if arg == "--select-ta":
            return args[idx+1]
    return ""


def grab_submission_comments(submission):
    if (len(submission.submission_comments) == 0):
        return []
    comments = []
    for comment in submission.submission_comments:
        date = comment['created_at']
        c = comment['comment']
        name = comment['author_name']
        comments.append("{0} - {1}: {2}".format(date, name, c))
    comments = "\n".join(sorted(comments))
    return comments

if __name__ == '__main__':
    course_id = sys.argv[1]
    path_template = sys.argv[2]
    path_destination = sys.argv[3]
    path_token = os.path.join(
        str(Path.home()),
        '.canvas.token'
    )
    select_section = '--select-section' in sys.argv
    select_ta = ta_file(sys.argv) # use --select-ta file.yaml

    resubmissions_only = '--resub' in sys.argv
    
    # sanity check
    with open(path_template, 'r') as f:
        template = parse_template(f.read())

    API_URL = 'https://absalon.ku.dk/'

    with open(path_token, 'r') as f:
        API_KEY = f.read().strip()


    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(course_id)

    assignments = sort_by_name(course.get_assignments())

    print('\nAssignments:')
    for n, assignment in enumerate(assignments):
        print('%2d :' % n, assignment.name)
    index = int(input('Select assignment: '))

    assignment = assignments[index]

    ta = None
    if select_ta:
        with open(select_ta, 'r') as f:
            try:
                (tas,stud) = parse_students_and_tas(f)
            except Exception as e:
                print(f"Failed to parse ta-list. Do all TA's have at least one student attached?\nexiting.")
                sys.exit(1)
        print('\nTAs:')
        for n, ta in enumerate(tas):
            print('%2d :' % n, ta)
        index = int(input('Select TA: '))

        ta = tas[index]
        students = []
        # Horrible hack to fetch users based on ku-ids
        for i in stud[index]:
            students += course.get_users(search_term=i,enrollment_type=['student'],
                                        enrollment_state='active')
    section = None
    if select_section:
        sections = sort_by_name(course.get_sections())

        print('\nSections:')
        for n, section in enumerate(sections):
            print('%2d :' % n, section.name)
        index = int(input('Select section: '))

        section = course.get_section(sections[index],
                                     include=['students', 'enrollments'])


    print(f'\nFetching: {assignment}')
    if select_ta:
        print(f'for {ta}')
    if select_section:
        print(f'from {section}')

    handins: Dict[str, Any] = {}
    participants = []
    empty_handins = []
    submissions = []

    if select_ta:
        submissions = [assignment.get_submission(s.id, include=['submission_comments']) for s in students]
    elif section:
        s_ids = [s['id'] for s in section.students if all([ e['enrollment_state'] == 'active'
                                                            for e in s['enrollments']])]
        submissions = section.get_multiple_submissions(assignment_ids=[assignment.id],
                                                       student_ids=s_ids,
                                                       include=['submission_comments'])
    else:
        submissions = assignment.get_submissions(include=['submission_comments'])

    for submission in submissions:
        user = course.get_user(submission.user_id)
        # add to participant list
        participants.append(
            create_student(
                user
            )
        )

        if hasattr(submission, 'attachments'):
            print(f'User {user.name} handed in something')
            # NOTE: This is a terribly hacky solution and should really be rewritten
            # collect which attachments to download
            # if only fetching resubmissions
            if  resubmissions_only:
                if hasattr(submission, 'score'):
                    print(f'Score: {submission.score}')
                    # If a submission has not yet been graded, submission.score will be None
                    if submission.score == None or submission.score < 1.0:
                        files = [s for s in submission.attachments]
                        # tag entire handin
                        uuid = '-'.join(sorted([a['uuid'] for a in files]))
                        try:
                            handins[uuid]['students'].append(user)
                        except KeyError:
                            handins[uuid] = {
                                'files': files,
                                'students': [user],
                                'comments': grab_submission_comments(submission)
                            }


            # else, grab everything
            else:
                files = [s for s in submission.attachments]

                # tag entire handin
                uuid = '-'.join(sorted([a['uuid'] for a in files]))
                try:
                    handins[uuid]['students'].append(user)
                except KeyError:
                    handins[uuid] = {
                        'files': files,
                        'students': [user],
                        'comments': grab_submission_comments(submission)
                    }
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

        # Count number of zip-files in handin
        num_zip_files = sum([1 if ".zip" in x['filename'].lower() or x['mime_class'] == 'zip' else 0 for x in handin['files']])
        if num_zip_files > 1:
            print(f"Submission contains {num_zip_files} files that look like zip-files.\nWill attempt to unzip into separate directories.")
            if template.onlineTA is not None:
                print("Will not submit to OnlineTA, due to multiple zip-files") 
        # download submission
        for attachment in handin['files']:
            # download attachment
            filename = attachment['filename']
            path = os.path.join(base, filename)
            data = download(attachment['url'])
            with open(path, 'wb') as bf:
                bf.write(data)

            # unzip attachments
            if attachment['mime_class'] == 'zip':
                unpacked = os.path.join(base, 'unpacked')
                # Some students might hand in multiple zip-files
                # if they do, unpack those files into uniquely-named directories
                if (num_zip_files > 1 or os.path.exists(unpacked)):
                    unpacked = os.path.join(base, "{0}_{1}".format(filename, '_unpacked'))
                    print(f"Attempting to unzip {filename} into {unpacked}")
                os.mkdir(unpacked)
                try:
                    with zipfile.ZipFile(path, 'r') as zip_ref:
                        try:
                            zip_ref.extractall(unpacked)
                            # Run through onlineTA, if the template gives a url
                            # and we have exactly 1 zip-file
                            if template.onlineTA is not None and num_zip_files == 1:
                                run_onlineTA(base, unpacked, template.onlineTA)
                        except NotADirectoryError:
                            print(f"Attempted to unzip into a non-directory: {name}")
                except BadZipFile:
                    print(f"Attached archive not a zip-file: {name}")
                except Exception as e:
                    print(f"Error when unzipping file {filename}.\nError message: {e}")
        # remove junk from submission directory
        junk = [
            '.git',
            '__MACOSX',
            '.stack-work',
            '.DS_Store'
        ]
        base_path = Path(base)
        for pattern in junk:
            for junk_path in base_path.rglob(pattern):
                try:
                    shutil.rmtree(junk_path)
                except NotADirectoryError:
                    os.remove(junk_path)


        # create grading sheet from template
        grade = os.path.join(base, 'grade.yml')
        sheet = create_sheet(template, handin['students'])
        with open(grade, 'w') as f:
            yaml.dump(sheet.serialize(), f)

        # Dump submission comments
        # empty python lists evaluate as False, so
        # we only dump if we have comments
        if (handin['comments']):
            comment_path = os.path.join(base, 'submission_comments.txt')
            # Be super safe and check if the student handed in a file named 'submission_comments.txt'
            # If it does exist, do some yeehaw renaming of the downloaded submission comments
            # from canvas
            if (os.path.exists(comment_path)):
                fname_i : int = 0
                while(os.path.exists(comment_path)):
                    fname_i += 1
                    comment_fname = 'submission_comments({0}).txt'.format(fname_i)
                    comment_path = os.path.join(base, comment_fname)

            with open(comment_path, 'w', encoding='utf-8-sig') as f:
                f.write(handin['comments'])

    # create a list of students with empty handins
    with open(empty, 'w') as f:
        yaml.dump(
            [create_student(p).serialize() for p in empty_handins],
            f
        )

    # create meta file
    with open(meta, 'w') as f:
        meta_data = Meta(
            course=MetaCourse(course.id, course.name),
            assignment=MetaAssignment(assignment.id, assignment.name,
                                      section=section.id if section else None),
        )
        yaml.dump(meta_data.serialize(), f)
