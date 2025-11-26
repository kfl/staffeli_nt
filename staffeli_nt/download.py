import argparse
import concurrent.futures
import hashlib
import os
import random
import re
import shutil
import sys
import threading
import zipfile
from pathlib import Path
from typing import Any, Dict, Tuple
from zipfile import BadZipFile

from canvasapi import Canvas  # type: ignore[import-untyped]
from canvasapi.exceptions import CanvasException, RateLimitExceeded  # type: ignore[import-untyped]

from .console import console, print_error, print_info, print_warning
from .util import download, run_onlineTA
from .vas import (
    Meta,
    MetaAssignment,
    MetaCourse,
    create_sheet,
    create_student,
    create_yaml,
    parse_students_and_tas,
    parse_template,
    yaml,
)

# Canvas API rate limit settings
MAX_API_WORKERS = 100
RATE_LIMIT_RETRY_DELAY = 2.0  # 2s wait when rate limited
MAX_RETRIES = 3
SUBMISSION_BUFFER_SIZE = 30  # Buffer size for pagination consumption


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
    return sorted(list(named), key=lambda x: smart_key(x.name))


def grab_submission_comments(submission) -> str:
    if not submission.submission_comments:
        return ''
    comments = [
        f'{c["created_at"]} - {c["author_name"]}: {c["comment"]}'
        for c in submission.submission_comments
    ]
    return '\n'.join(sorted(comments))


def get_student_ids(canvas, course, course_id, select_ta, select_section, tas, stud):
    """
    Get list of student IDs based on selection criteria.

    Returns:
        tuple: (student_ids, section) where section is None unless select_section is True
    """
    section = None

    if select_ta:
        console.print('\n[info]TAs:[/info]')
        for n, ta_name in enumerate(tas):
            console.print(f'{n:2d} : {ta_name}')
        index = int(input('Select TA: '))
        students = []
        for i in stud[index]:
            # Need full user lookup for search_term matching
            students += course.get_users(
                search_term=i, enrollment_type=['student'], enrollment_state='active'
            )
        student_ids = [s.id for s in students]

    elif select_section:
        sections = sort_by_name(course.get_sections())
        console.print('\n[info]Sections:[/info]')
        for n, sec in enumerate(sections):
            console.print(f'{n:2d} : {sec.name}')
        index = int(input('Select section: '))
        section = course.get_section(sections[index].id, include=['students', 'enrollments'])
        student_ids = [
            s['id']
            for s in section.students
            if all(e['enrollment_state'] == 'active' for e in s['enrollments'])
        ]
    else:
        # Get all enrolled students using GraphQL (faster - only fetches IDs)
        # Note: We query enrollments rather than users because Canvas GraphQL doesn't
        # provide a way to query unique users with enrollment filtering. Students with
        # multiple enrollments (e.g., in different sections) will appear multiple times,
        # so we must deduplicate by user ID on the client side.

        query = """
        query($courseId: ID!, $cursor: String) {
          course(id: $courseId) {
            enrollmentsConnection(
              filter: {types: StudentEnrollment, states: active}
              first: 100
              after: $cursor
            ) {
              nodes {
                user {
                  _id
                }
              }
              pageInfo {
                endCursor
                hasNextPage
              }
            }
          }
        }
        """

        def fetch_all_enrollments():
            """Generator that yields all enrollment user IDs across all pages."""
            cursor = None
            has_next_page = True

            while has_next_page:
                variables = {'courseId': course_id, 'cursor': cursor}
                result = canvas.graphql(query, variables=variables)
                enrollments = result['data']['course']['enrollmentsConnection']

                # Yield all user IDs from this page
                yield from (int(node['user']['_id']) for node in enrollments['nodes'])

                # Update pagination state
                page_info = enrollments['pageInfo']
                has_next_page = page_info['hasNextPage']
                cursor = page_info['endCursor']

        # Deduplicate user IDs (students may appear in multiple enrollments)
        student_ids = list(set(fetch_all_enrollments()))

    return student_ids, section


def validate_inputs(path_destination: str, path_template: str, select_ta: str | None):
    """Validate all local inputs before making network requests.

    Returns:
        tuple: (template, tas, stud) where tas and stud are None if select_ta is not used
    """
    if os.path.exists(path_destination):
        print_error(
            f"Destination directory '{path_destination}' already exists.\n"
            'Please choose a different directory name or remove the existing directory.'
        )
        sys.exit(1)

    try:
        with open(path_template, 'r') as f:
            template = parse_template(f.read())
    except FileNotFoundError:
        print_error(f"Template file '{path_template}' not found.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to parse template file '{path_template}'\nReason: {e}")
        sys.exit(1)

    tas = None
    stud = None
    if select_ta is not None:
        try:
            with open(select_ta, 'r') as f:
                (tas, stud) = parse_students_and_tas(f)
        except FileNotFoundError:
            print_error(f"TA list file '{select_ta}' not found.")
            sys.exit(1)
        except Exception as e:
            print_error(
                f"Failed to parse TA list file '{select_ta}'\n"
                f'Reason: {e}\n'
                'Do all TAs have at least one student attached?'
            )
            sys.exit(1)

    return (template, tas, stud)


def process_submission(
    student_id, assignment, course, resubmissions_only, cancel_event, retry_count=0
):
    """
    Fetches and processes a single submission for a student.
    Handles its own rate limiting with retries and random jitter.
    Uses cancel_event to allow interrupting retry delays.
    """
    try:
        submission = assignment.get_submission(student_id, include=['submission_comments'])
        user = course.get_user(student_id)
    except (RateLimitExceeded, CanvasException) as e:
        # Check if it's a rate limit error (status 429)
        if '429' in str(e) or isinstance(e, RateLimitExceeded):
            if retry_count < MAX_RETRIES:
                # Add random jitter (0-500ms) to avoid thundering herd problem
                jitter = random.uniform(0, 0.5)
                delay = RATE_LIMIT_RETRY_DELAY + jitter
                print_warning(
                    f'Rate limit exceeded, retrying in {delay:.2f}s... '
                    f'(attempt {retry_count + 1}/{MAX_RETRIES})'
                )
                # Use interruptible wait instead of sleep
                if cancel_event.wait(delay):
                    # Event was set, we're shutting down
                    raise InterruptedError('Operation cancelled during retry')
                return process_submission(
                    student_id,
                    assignment,
                    course,
                    resubmissions_only,
                    cancel_event,
                    retry_count + 1,
                )
            print_error(f'Rate limit exceeded after {MAX_RETRIES} retries, giving up')
        raise

    result = {'user': user, 'is_empty': True}  # Assume empty by default

    if hasattr(submission, 'attachments') and len(submission.attachments) > 0:
        print_info(f'User {user.name} handed in something')
        # NOTE: This is a terribly hacky solution and should really be rewritten
        # collect which attachments to download
        # if only fetching resubmissions
        if resubmissions_only:
            if hasattr(submission, 'score'):
                print_info(f'Score: {submission.score}')
                # If a submission has not yet been graded, submission.score will be None
                if submission.score is None or submission.score < 1.0:
                    files = [s for s in submission.attachments]
                    # tag entire handin
                    uuid = '-'.join(sorted([a.uuid for a in files]))
                    handin_data = {
                        'files': files,
                        'students': [user],
                        'comments': grab_submission_comments(submission),
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
                'comments': grab_submission_comments(submission),
            }
            result.update({'is_empty': False, 'uuid': uuid, 'handin_data': handin_data})

    return result


def process_handin(item: Tuple[str, Dict[str, Any]], home: str, template: Any):
    """
    Processes a single handin: downloads files, creates directories, and generates grading sheets.
    This function is designed to be run in a parallel executor.
    """
    # Create a local YAML instance for this thread (ruamel.yaml is not thread-safe)
    local_yaml = create_yaml()

    uuid, handin = item
    student_names = ', '.join([u.name for u in handin['students']])
    print_info(f'Downloading submission from: {student_names}')

    # create submission directory
    name = '-'.join(sorted([kuid(u.login_id) for u in handin['students']]))
    base = os.path.join(home, name)
    os.mkdir(base)

    # Count number of zip-files in handin
    num_zip_files = sum(
        1 for x in handin['files'] if '.zip' in x.filename.lower() or x.mime_class == 'zip'
    )
    if num_zip_files > 1:
        print_warning(
            f'Submission contains {num_zip_files} files that look like zip-files.\n'
            'Will attempt to unzip into separate directories.'
        )
        if template.onlineTA is not None:
            print_warning('Will not submit to OnlineTA, due to multiple zip-files')

    # download submission
    for attachment in handin['files']:
        # download attachment
        filename = attachment.filename
        path = os.path.join(base, filename)
        try:
            data = download(attachment.url)
            with open(path, 'wb') as bf:
                bf.write(data)
        except Exception as e:
            error_msg = (
                f'Failed to download file: {filename}\n'
                f'From: {student_names}\n'
                f'Submission directory: {base}\n'
                f'URL: {attachment.url}\n'
                f'Error: {e}'
            )
            print_error(error_msg)
            raise RuntimeError(error_msg) from e

        # unzip attachments
        if attachment.mime_class == 'zip':
            unpacked = os.path.join(base, 'unpacked')
            if num_zip_files > 1 or os.path.exists(unpacked):
                unpacked = os.path.join(base, f'{filename}_unpacked')
                print_info(f'Attempting to unzip {filename} into {unpacked}')
            os.mkdir(unpacked)
            try:
                with zipfile.ZipFile(path, 'r') as zip_ref:
                    try:
                        zip_ref.extractall(unpacked)
                        if template.onlineTA is not None and num_zip_files == 1:
                            run_onlineTA(base, unpacked, template.onlineTA)
                    except NotADirectoryError:
                        print_error(f'Attempted to unzip into a non-directory: {name}')
            except BadZipFile:
                print_warning(f'Attached archive not a zip-file: {name}')
            except Exception as e:
                print_error(f'Error when unzipping file {filename}\nError message: {e}')

    # remove junk from submission directory
    junk = ['.git', '__MACOSX', '.stack-work', '.DS_Store']
    base_path = Path(base)
    for pattern in junk:
        for junk_path in base_path.rglob(pattern):
            try:
                shutil.rmtree(junk_path)
            except NotADirectoryError:
                os.remove(junk_path)

    # create grading sheet from template
    grade = os.path.join(base, 'grade.yml')
    sheet = create_sheet(template, sorted(handin['students'], key=lambda u: u.login_id))
    with open(grade, 'w') as f:
        local_yaml.dump(sheet.serialize(), f)

    # Dump submission comments
    if handin['comments']:
        comment_path = os.path.join(base, 'submission_comments.txt')
        if os.path.exists(comment_path):
            fname_i = 0
            while os.path.exists(comment_path):
                fname_i += 1
                comment_path = os.path.join(base, f'submission_comments({fname_i}).txt')
        with open(comment_path, 'w', encoding='utf-8-sig') as f:
            f.write(handin['comments'])


def add_subparser(subparsers: argparse._SubParsersAction):
    parser: argparse.ArgumentParser = subparsers.add_parser(
        name='download', help='fetch submissions'
    )
    parser.add_argument('course_id', type=str, metavar='INT', help='the course id')
    parser.add_argument(
        'path_template', type=str, metavar='TEMPLATE_PATH', help='path to the YAML template'
    )
    parser.add_argument(
        'path_destination',
        type=str,
        metavar='SUBMISSIONS_PATH',
        help='destination to submissions folder',
    )
    parser.add_argument(
        '--select-section', action='store_true', help='whether section selection is used'
    )
    parser.add_argument(
        '--select-ta', type=str, metavar='PATH', help='path to a YAML file with TA distributions'
    )
    parser.add_argument(
        '--resub', action='store_true', help='whether only resubmissions should be fetched'
    )
    parser.add_argument(
        '--buffersize',
        type=int,
        default=SUBMISSION_BUFFER_SIZE,
        metavar='N',
        help=f'buffer size for pagination consumption (default: {SUBMISSION_BUFFER_SIZE})',
    )
    parser.set_defaults(main=main)


def main(api_url, api_key, args: argparse.Namespace):
    course_id = args.course_id
    path_template = args.path_template
    path_destination = args.path_destination
    select_section = args.select_section
    select_ta = args.select_ta
    resubmissions_only = args.resub
    buffersize = args.buffersize

    template, tas, stud = validate_inputs(path_destination, path_template, select_ta)

    # --- Sequential Setup Phase ---
    canvas = Canvas(api_url, api_key)
    course = canvas.get_course(course_id)
    assignments = sort_by_name(course.get_assignments())

    console.print('\n[info]Assignments:[/info]')
    for n, assignment in enumerate(assignments):
        console.print(f'{n:2d} : {assignment.name}')
    index = int(input('Select assignment: '))
    assignment = assignments[index]

    # Get student IDs based on selection criteria (TA/section/all)
    student_ids, section = get_student_ids(
        canvas, course, course_id, select_ta, select_section, tas, stud
    )

    os.mkdir(path_destination)

    handins: Dict[str, Any] = {}
    participants = []
    empty_handins = []

    # Process submissions by fetching them in parallel from student IDs
    # Create event for cancelling workers (used to interrupt retry delays)
    cancel_event = threading.Event()

    # --- Unified Parallel Execution using a single Executor ---
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_API_WORKERS)
    try:
        # --- Phase 1: Fetch and process submissions in parallel (one per student) ---
        print_info(f'Processing {len(student_ids)} submissions in parallel...')
        processed_results = list(
            executor.map(
                lambda sid: process_submission(
                    sid, assignment, course, resubmissions_only, cancel_event
                ),
                student_ids,
                buffersize=buffersize,
            )
        )

        # --- Phase 2: Reduce results to build handins dictionary ---
        for result in processed_results:
            user = result['user']
            participants.append(create_student(user))
            if result['is_empty']:
                empty_handins.append(user)
            else:
                uuid = result['uuid']
                # This logic keeps the comments from the first-processed submission
                # and assumes for a group hand-in, all comments are identical.
                if uuid in handins:
                    handins[uuid]['students'].append(user)
                else:
                    handins[uuid] = result['handin_data']

        # --- Phase 3: Download handins in parallel ---
        print_info('Downloading submissions')

        # process_handin doesn't return anything, so we just consume the iterator
        list(
            executor.map(
                lambda item: process_handin(item, path_destination, template), handins.items()
            )
        )
    except Exception as e:
        # Determine error type and show appropriate message
        print_error('Error occurred during processing of submissions:')

        console.print()  # Blank line
        print_warning('Cancelling pending tasks and waiting for running tasks to complete...')
        # Signal all workers to stop (interrupts retry delays)
        cancel_event.set()
        executor.shutdown(wait=True, cancel_futures=True)
        print_info('Shutdown complete.')

        # Check if it's a rate limit error by walking the exception chain
        is_rate_limit = '429' in str(e) or isinstance(e, RateLimitExceeded)
        if not is_rate_limit:
            current = e.__cause__
            while current and not is_rate_limit:
                is_rate_limit = '429' in str(current) or isinstance(current, RateLimitExceeded)
                current = current.__cause__

        if is_rate_limit:
            print_error(
                'Canvas API rate limit exceeded.\n'
                f'Try again in a moment, or use --buffersize with a lower value '
                f'(currently {buffersize}).'
            )
        else:
            error_msg = str(e)
            if e.__cause__:
                error_msg += f'\nCaused by: {e.__cause__}'
            print_error(error_msg)

        raise
    else:
        # Normal shutdown: wait for all tasks to complete
        executor.shutdown(wait=True)

    # --- Final Sequential File Writes ---
    with open(os.path.join(path_destination, 'empty.yml'), 'w') as f:
        yaml.dump(
            [
                create_student(p).serialize()
                for p in sorted(empty_handins, key=lambda u: u.login_id)
            ],
            f,
        )

    with open(os.path.join(path_destination, 'meta.yml'), 'w') as f:
        meta_data = Meta(
            course=MetaCourse(course.id, course.name),
            assignment=MetaAssignment(
                assignment.id, assignment.name, section=section.id if section else None
            ),
        )
        yaml.dump(meta_data.serialize(), f)
