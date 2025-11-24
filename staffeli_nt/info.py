import sys
import argparse
import hashlib
import re
import math
from .vas import *
from .util import *
from typing import Dict, Any


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


# Write the ta_list that can be given as input to staffeli
# in order to download only specified assignments
def write_ta_list(distribution, fname):
    with open(fname, 'w') as ta_list_file:
        for sectionname, ids in distribution.items():
            # Only write entry if there are actually any handins
            if len(ids) > 0:
                # First do a stupid conversion to remove any duplicates
                # There shouldn't be any, but JIC
                list_ids = list(set(ids))
                # If this is a group handin, split the group-members' ids onto multiple lines
                fixed_ids = ['- ' + x.replace('-', '\n- ') + '\n' for x in list_ids]
                idlist = ''.join(fixed_ids)
                entry = '\n{0}:\n{1}\n'.format(sectionname, idlist)
                ta_list_file.write(entry)


# We have some sections that are useless,
# Try to remove them, in a nice and hardcoded way only suitable for PoP
# Grab the items (handins) in useless sections and put them in a list to return
def clean_up_bags(bags):
    unass_ass = []
    keys_to_remove = []
    for key in bags.keys():
        if 'hold' not in key.lower():
            for item in bags[key]:
                unass_ass.append(item)
            keys_to_remove.append(key)
    for key in keys_to_remove:
        del bags[key]
    return unass_ass


# Given a dictionary of section,handins
# distribute such that each bag has approximately the same amount of handins
def distribute(bags, verbose=True, debug=False):
    # First clean up the bags, grabbing all "phony section" submissions in the process
    unass_ass_stack = clean_up_bags(bags)  # I am still great at naming variables
    # Figure out how many bags we have, how many handins we have and calculate an average
    num_handins = len(unass_ass_stack)
    num_bags = 0
    for key, handins in bags.items():
        num_handins += len(handins)
        num_bags += 1
    # Each bag should contain at most avg, the number of handins / number of TAs, rounded up
    avg = math.ceil(num_handins / num_bags)
    if verbose or debug:
        print(f'[INFO] Total: {num_handins}')
        print(f'[INFO] TAs: {num_bags}')
        print(f'[INFO] Avg, rounded up: {avg}')
        print(f'[INFO] Initial unassigned submissions: {len(unass_ass_stack)}')

    # The general algorithm:
    #    1) Sort the bags in order of descending number of handins
    #    2) Create an empty stack to hold unassigned submissions
    #    3) For each bag:
    #        if overfull, remove submissions by pushing them to the stack
    #        else, add submissions by popping from the stack
    #    4) while bag(s) exist with < (avg-1) submissions exist:
    #           redistribute submission from a bag with >= avg submissions

    if verbose or debug:
        print('[INFO] Before redistribution:')
        print('{0:32}handins'.format('Hold'))
        for key, handins in bags.items():
            print('{0:32}{1}'.format(key, len(handins)))

    # We iterate over all bags, sorted in order of descending number of handins
    baglist = sorted(
        [(len(handins), key) for (key, handins) in bags.items()], key=lambda x: x[0], reverse=True
    )

    for handins, key in baglist:
        # Will loop if bag has too many handins
        for _ in range(handins - avg):
            unass_ass_stack.append(bags[key].pop())
        # will loop if bag has too few handins
        for _ in range(avg - handins - 1):
            # We might pop from an empty stack, so we catch the exception and just redistribute further later
            try:
                bags[key].append(unass_ass_stack.pop())
            except:
                break

    # Hold that has too few submissions
    nonfull = list(
        filter(lambda x: x[0] < (avg - 1), [(len(handins), key) for (key, handins) in bags.items()])
    )
    # Hold that has "too many" submissions
    full = list(
        filter(lambda x: x[0] >= avg, [(len(handins), key) for (key, handins) in bags.items()])
    )
    if debug:
        print(f'[DEBUG] Nonfull bags:\n{nonfull}\n[DEBUG] Full bags:\n{full}')

    for handins, key in nonfull:
        if (avg - handins - 1) > len(full):
            print(
                f'[!!!] INTERNAL ERROR: Ran out of submissions to redistribute. Skipping redistribution.'
            )
            break
        if debug:
            print(f'{key} needs {avg - handins - 1} submissions. We have {len(full)} to give out.')
        for _ in range(avg - handins - 1):
            try:
                fh, fk = full[0]
                bags[key].append(bags[fk].pop())
                full.remove((fh, fk))
            except:
                print(f'[!] INTERNAL ERROR: Ran out of submissions to redistribute to {key}.')
                break

    final_num_handins = 0
    for key, handins in bags.items():
        final_num_handins += len(handins)
    if verbose or debug:
        print(
            f'[***] SANITY CHECK:\n\tOriginal number of handins: {num_handins}\n\tFinal number of handins:    {final_num_handins}'
        )
        if num_handins != final_num_handins:
            print(
                '[!!!] FATAL ERROR: Final number of submissions is not equal to the original number. Something went terribly wrong.'
            )
        print(f'[INFO] Done redistributing {num_handins} handins between {num_bags} TAs.')
        print('{0:32}handins'.format('Hold'))
        for key, handins in bags.items():
            print('{0:32}{1}'.format(key, len(handins)))

    return bags


# Fetch submissions/handins for an assignment
# construct a dictionary of (sectionname,[handins]) where
#     [handins] is a list of ku-id's
#               either singular or joined by '-' for group assignments
# returns: the constructed dictionary
def get_handins_by_sections(course: Any) -> Dict[str, list[str]]:
    assignments = sort_by_name(course.get_assignments())
    print('\nAssignments:')
    for n, assignment in enumerate(assignments):
        print('%2d :' % n, assignment.name)
    index = int(input('Select assignment: '))

    # Preinitialize the "bags" with course_section_name
    users_and_sections: Dict[str, Any] = {}
    sections = sorted(list(course.get_sections()), key=lambda x: x.name)

    # From the user.enrollments we only have the section_id
    # Normal people prefer reading the section_name
    # secname_lookup is a dictionary that translates id to name
    secname_lookup = {}
    for section in sections:
        users_and_sections[section.name] = []
        secname_lookup[section.id] = section.name

    assignment = assignments[index]
    handins: Dict[str, Any] = {}
    submissions = []
    submissions = assignment.get_submissions()
    for submission in submissions:
        user = course.get_user(submission.user_id, include=['enrollments'])

        if hasattr(submission, 'attachments') and len(submission.attachments) > 0:
            print(f'User {user.name} handed in something')
            # each section is a key, pointing to a list of ku_id
            # user.enrollments[0] is the first enrollment for the user.
            # This *might* become problematic, wrt. section changes etc.
            files = [s for s in submission.attachments]
            # tag entire handin, by joining uuid for each file in the handin
            uuid = '-'.join(sorted([a.uuid for a in files]))
            try:
                handins[uuid]['students'].append(user)
            except KeyError:
                handins[uuid] = {'files': files, 'students': [user]}

    # handins contains all the submissions, grouped by group
    num_handins = len(handins)

    print(f'Number of handins: {num_handins}')

    for uuid, handin in handins.items():
        try:
            student_names = ', '.join([u.name for u in handin['students']])
            ku_ids = '-'.join([kuid(u.login_id) for u in handin['students']])
            # If a group assignment has students from multiple sections,
            # just grab the first section and pretend they all belong to that one
            handin_section = secname_lookup[
                handin['students'][0].enrollments[0]['course_section_id']
            ]
            users_and_sections[handin_section].append(ku_ids)

        except Exception as e:
            print('Oh boy, something went terribly wrong when finding users from assignment')
            print(f'{e}\n')

    return users_and_sections


def create_and_write_assignment_distribution(course, fname, verbose=True, debug=False):
    handins = get_handins_by_sections(course)
    distributed_handins = distribute(handins, verbose, debug)
    write_ta_list(distributed_handins, fname)


def get_section_info(course):
    sections = sorted(list(course.get_sections()), key=lambda x: x.name)

    for n, section in enumerate(sections):
        print('%2d : ' % n, section.name)
    index = int(input('Which section: '))

    section = sections[index]
    print('Fetching:', section)

    students = course.get_users(
        enrollment_type='student', enrollment_state='active', include=['enrollments']
    )
    print('kuid,name')
    for student in students:
        if student.enrollments[0]['course_section_id'] == section.id:
            print('%6s,' % kuid(student.email), student.name)


def get_course(api_url, api_key, course_id):
    return Canvas(api_url, api_key).get_course(course_id)


def add_subparser(subparsers: argparse._SubParsersAction):
    parser: argparse.ArgumentParser = subparsers.add_parser(
        name='info', help='fetch infomation related to a course'
    )
    parser.add_argument('course_id', type=str, metavar='INT', help='the course id')
    parser.add_argument('--quiet', action='store_true', help='disable verbose output')
    parser.add_argument('--debug', action='store_true', help='enable debug printing')
    parser.add_argument(
        '--get-ass-dist',
        metavar='PATH',
        help=(
            "select an assignment and construct a distribution between available TA's, resulting in a YAML-file suitable for using with the --select-ta flag in download subcommand where the result will be written to PATH"
        ),
    )
    parser.add_argument('--ids', action='store_true', help='print kuids and names for a sections')
    parser.set_defaults(main=main)


def main(api_url, api_key, args: argparse.Namespace):
    course_id = args.course_id
    verbose = not args.quiet
    debug = args.debug
    fname = args.get_ass_dist
    ids = args.ids

    canvas = Canvas(api_url, api_key)
    try:
        course = canvas.get_course(course_id)
    except:
        print('Failed to parse course id.')
        sys.exit(1)

    if fname is not None:
        course = get_course(api_url, api_key, course_id)
        create_and_write_assignment_distribution(course, fname, verbose, debug)
    elif ids:
        course = get_course(api_url, api_key, course_id)
        get_section_info(course)
    else:
        print('Non-valid arguments.')
        sys.exit(1)
