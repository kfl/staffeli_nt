import os
import sys
import shutil
import zipfile
import hashlib
import re
from zipfile import BadZipFile
from pathlib import Path
from typing import Dict, Any
import argparse
import concurrent.futures

from .vas import *
from .util import *

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

def grab_submission_comments(submission) -> str:
    if len(submission.submission_comments) == 0:
        return ""
    comments = []
    for comment in submission.submission_comments:
        date = comment['created_at']
        c = comment['comment']
        name = comment['author_name']
        comments.append("{0} - {1}: {2}".format(date, name, c))
    return "\n".join(sorted(comments))

def add_subparser(subparsers: argparse._SubParsersAction):
    parser : argparse.ArgumentParser = subparsers.add_parser(name='download', help='fetch submissions')
    parser.add_argument('course_id', type=str, metavar='INT', help='the course id')
    parser.add_argument('path_template', type=str, metavar='TEMPLATE_PATH', help='path to the YAML template')
    parser.add_argument('path_destination', type=str, metavar='SUBMISSIONS_PATH', help='destination to submissions folder')
    parser.add_argument('--select-section', action='store_true', help='whether section selection is used')
    parser.add_argument('--select-ta', type=str, metavar='PATH', help='path to a YAML file with TA distributions')
    parser.add_argument('--resub', action='store_true', help='whether only resubmissions should be fetched')
    parser.set_defaults(main=main)


def validate_inputs(path_destination: str, path_template: str, select_ta: str | None):
    """Validate all local inputs before making network requests.

    Returns:
        tuple: (template, tas, stud) where tas and stud are None if select_ta is not used
    """
    if os.path.exists(path_destination):
        print(f"Error: Destination directory '{path_destination}' already exists.")
        print("Please choose a different directory name or remove the existing directory.")
        sys.exit(1)

    try:
        with open(path_template, 'r') as f:
            template = parse_template(f.read())
    except FileNotFoundError:
        print(f"Error: Template file '{path_template}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to parse template file '{path_template}'")
        print(f"Reason: {e}")
        sys.exit(1)

    tas = None
    stud = None
    if select_ta is not None:
        try:
            with open(select_ta, 'r') as f:
                (tas, stud) = parse_students_and_tas(f)
        except FileNotFoundError:
            print(f"Error: TA list file '{select_ta}' not found.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Failed to parse TA list file '{select_ta}'")
            print(f"Reason: {e}")
            print("Do all TAs have at least one student attached?")
            sys.exit(1)

    return (template, tas, stud)


def process_submission(submission, course, resubmissions_only):
    """
    Processes a single submission to fetch user data and prepare handin info.
    This function is designed to be run in a parallel executor.
    """
    user = course.get_user(submission.user_id)
    result = {'user': user, 'is_empty': True} # Assume empty by default

    if hasattr(submission, 'attachments') and len(submission.attachments) > 0:
        print(f'User {user.name} handed in something')
        # NOTE: This is a terribly hacky solution and should really be rewritten
        # collect which attachments to download
        # if only fetching resubmissions
        if resubmissions_only:
            if hasattr(submission, 'score'):
                print(f'Score: {submission.score}')
                # If a submission has not yet been graded, submission.score will be None
                if submission.score is None or submission.score < 1.0:
                    files = [s for s in submission.attachments]
                    # tag entire handin
                    uuid = '-'.join(sorted([a.uuid for a in files]))
                    handin_data = {
                        'files': files,
                        'students': [user],
                        'comments': grab_submission_comments(submission)
                    }
                    result.update({'is_empty': False, 'uuid': uuid, 'handin_data': handin_data})
        # else, grab everything
        else:
            files = [s for s in submission.attachments]

            # tag entire handin
            uuid = '-'.join(sorted([a.uuid for a in files]))
            handin_data = {
                'files': files,
                'students': [user],
                'comments': grab_submission_comments(submission)
            }
            result.update({'is_empty': False, 'uuid': uuid, 'handin_data': handin_data})

    return result


def main(api_url, api_key, args: argparse.Namespace):
    course_id = args.course_id
    path_template = args.path_template
    path_destination = args.path_destination
    select_section = args.select_section
    select_ta = args.select_ta
    resubmissions_only = args.resub

    template, tas, stud = validate_inputs(path_destination, path_template, select_ta)

    canvas = Canvas(api_url, api_key)
    course = canvas.get_course(course_id)

    assignments = sort_by_name(course.get_assignments())

    print('\nAssignments:')
    for n, assignment in enumerate(assignments):
        print('%2d :' % n, assignment.name)
    index = int(input('Select assignment: '))

    assignment = assignments[index]

    ta = None
    if select_ta is not None:
        print('\nTAs:')
        for n, ta in enumerate(tas):
            print('%2d :' % n, ta)
        index = int(input('Select TA: '))

        ta = tas[index]
        students = []
        # Horrible hack to fetch users based on ku-ids
        for i in stud[index]:
            students += course.get_users(search_term=i, enrollment_type=['student'],
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
    if select_ta is not None:
        print(f'for {ta}')
    if select_section:
        print(f'from {section}')

    handins: Dict[str, Any] = {}
    participants = []
    empty_handins = []
    submissions = []

    if select_ta is not None:
        submissions = [assignment.get_submission(s.id, include=['submission_comments']) for s in students]
    elif section is not None:
        s_ids = [s['id'] for s in section.students if all([ e['enrollment_state'] == 'active'
                                                            for e in s['enrollments']])]
        submissions = section.get_multiple_submissions(assignment_ids=[assignment.id],
                                                       student_ids=s_ids,
                                                       include=['submission_comments'])
    else:
        submissions = assignment.get_submissions(include=['submission_comments'])

    # --- Parallel "Map" Phase ---
    # Process submissions in parallel to fetch user data and prepare handin info
    processed_results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_submission = {executor.submit(process_submission, s, course, resubmissions_only): s for s in submissions}
        for future in concurrent.futures.as_completed(future_to_submission):
            try:
                processed_results.append(future.result())
            except Exception as e:
                print(f"An error occurred while processing a submission: {e}")

    # --- Sequential "Reduce" Phase ---
    # Consolidate the results from the parallel phase into the final data structures
    for result in processed_results:
        user = result['user']
        participants.append(create_student(user))

        if result['is_empty']:
            empty_handins.append(user)
        else:
            uuid = result['uuid']
            handin_data = result['handin_data']
            # NOTE on group hand-ins: This logic keeps the comments from the first-processed
            # submission and discards comments from other group members. This assumes that
            # for a group hand-in, all submission comments are identical.
            try:
                # If handin (by content) already exists, append student
                handins[uuid]['students'].append(user)
            except KeyError:
                # Otherwise, add the new handin
                handins[uuid] = handin_data


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
        name = '-'.join(sorted([kuid(u.login_id) for u in handin['students']]))
        base = os.path.join(home, name)
        os.mkdir(base)

        # Count number of zip-files in handin
        num_zip_files = sum([1 if ".zip" in x.filename.lower() or x.mime_class == 'zip' else 0 for x in handin['files']])
        if num_zip_files > 1:
            print(f"Submission contains {num_zip_files} files that look like zip-files.\nWill attempt to unzip into separate directories.")
            if template.onlineTA is not None:
                print("Will not submit to OnlineTA, due to multiple zip-files")
        # download submission
        for attachment in handin['files']:
            # download attachment
            filename = attachment.filename
            path = os.path.join(base, filename)
            data = download(attachment.url)
            with open(path, 'wb') as bf:
                bf.write(data)

            # unzip attachments
            if attachment.mime_class == 'zip':
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
        sheet = create_sheet(template, sorted(handin['students'],
                                              key=lambda u: u.login_id))
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
            [create_student(p).serialize()
             for p in sorted(empty_handins, key=lambda u: u.login_id)],
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
