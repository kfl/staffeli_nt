#!/usr/bin/env python3

import os
import sys
import shutil
import hashlib
from pathlib import Path
import re
import math
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


# Write the ta_list that can be given as input to staffeli
# in order to download only specified assignments
def write_ta_list(distribution, fname):
    with open(fname, 'w') as ta_list_file:
        for (sectionname, ids) in distribution.items():
            # Only write entry if there are actually any handins
            if (len(ids) > 0):
                # First do a stupid conversion to remove any duplicates
                # There shouldn't be any, but JIC
                list_ids = list(set(ids))
                # If this is a group handin, split the group-members' ids onto multiple lines
                fixed_ids = ["- " + x.replace("-", "\n- ") + "\n" for x in list_ids]
                idlist = ''.join(fixed_ids)
                entry = "\n{0}:\n{1}\n".format(sectionname, idlist)
                ta_list_file.write(entry)



# We have some sections that are useless,
# Try to remove them, in a nice and hardcoded way only suitable for PoP
def clean_up_bags(bags):
    # print(f'Keys before:\n{bags.keys()}')
    keys_to_remove = []
    for key in bags.keys():
        if ("hold" not in key.lower()):
            keys_to_remove.append(key)
    for key in keys_to_remove:
        del bags[key]


# Given a dictionary of section,handins
# distribute such that each bag has approximately the same amount of handins
def distribute(bags):
    # Figure out how many bags we have
    # and how many handins we have
    # to calculate an average
    num_handins = 0
    num_bags = 0
    for (key,handins) in bags.items():
        num_handins += len(handins)
        num_bags += 1
    # Each bag should contain at most avg, the number of handins / number of TAs, rounded up
    avg = math.ceil(num_handins / num_bags)

    # First pop all overflowing bags until they have the perfect amount of handins.
    # Then split the bags into two sets:
    # 1) bags with the perfect amount of handins
    # 2) bags with too few handins
    # While there exist unassigned handins:
    #     assign the first available handin to the first available bag
    full_bags: Dict[str, Any] = {}
    non_full_bags: Dict[str, Any] = {}
    unass_ass = [] # I am great at naming variables

    for (key,handins) in bags.items():
        num_in_bag = len(handins)
        while (num_in_bag) > avg:
            unass_ass.append(handins.pop())
            num_in_bag -= 1
        if (num_in_bag < avg):
            non_full_bags[key] = handins
        else:
            full_bags[key] = handins

    while (len(unass_ass) > 0):
        for (key,handins) in non_full_bags.items():
            # We might pop from an empty list, so chicken out and do the bare minimum
            # to finish our stupid algorithm without errors
            try:
                non_full_bags[key].append(unass_ass.pop())
            except:
                break

    # At this point, all bags should be as full as possible
    for key in non_full_bags.keys():
        full_bags[key] = non_full_bags[key]

    return full_bags


# Fetch submissions/handins for an assignment
# construct a dictionary of (sectionname,[handins]) where
#     [handins] is a list of ku-id's
#               either singular or joined by '-' for group assignments
# returns: the constructed dictionary
def get_handins_by_sections(course):
    assignments = sort_by_name(course.get_assignments())
    print('\nAssignments:')
    for n, assignment in enumerate(assignments):
        print('%2d :' % n, assignment.name)
    index = int(input('Select assignment: '))

    # Preinitialize the "bags" with course_section_name
    users_and_sections: Dict[str, Any] = {}
    sections = sorted(
        list(course.get_sections()),
        key=lambda x: x.name)

    # From the user.enrollments we only have the section_id
    # Normal people prefer reading the section_name
    # secname_lookup is a dictionary that translates id to name
    secname_lookup = {}
    for section in sections:
        users_and_sections[section.name] = []
        secname_lookup[section.id] = section.name


    assignment = assignments[index]
    handins: Dict[str, Any] = {}
    participants = []
    empty_handins = []
    submissions = []
    submissions = assignment.get_submissions()
    for submission in submissions:
        user = course.get_user(submission.user_id, include=['enrollments'])

        if hasattr(submission, 'attachments'):
            print(f'User {user.name} handed in something')
            # each section is a key, pointing to a list of ku_id
            # user.enrollments[0] is the first enrollment for the user.
            # This *might* become problematic, wrt. section changes etc. 
            files = [s for s in submission.attachments]
            # tag entire handin, by joining uuid for each file in the handin
            uuid = '-'.join(sorted([a['uuid'] for a in files]))
            try:
                handins[uuid]['students'].append(user)
            except KeyError:
                handins[uuid] = {
                    'files': files,
                    'students': [user]
                }

    # handins contains all the submissions, grouped by group
    num_handins = len(handins)

    print(f"Number of handins: {num_handins}")

    for (uuid, handin) in handins.items():
        try:
            student_names = ', '.join([u.name for u in handin['students']])
            ku_ids = '-'.join([kuid(u.login_id) for u in handin['students']])
            # If a group assignment has students from multiple sections,
            # just grab the first section and pretend they all belong to that one    
            handin_section = secname_lookup[handin['students'][0].enrollments[0]["course_section_id"]]
            users_and_sections[handin_section].append(ku_ids)

        except Exception as e:
            print("Oh boy, something went terribly wrong when finding users from assignment")
            print(f'{e}\n')

    return users_and_sections


def create_and_write_assignment_distribution(course, fname):
    handins = get_handins_by_sections(course)
    clean_up_bags(handins)
    distributed_handins = distribute(handins)
    write_ta_list(distributed_handins, fname)


def get_section_info(course):
    sections = sorted(
        list(course.get_sections()),
        key=lambda x: x.name)

    for n, section in enumerate(sections):
        print('%2d : ' % n, section.name)
    index = int(input('Which section: '))

    section = sections[index]
    print('Fetching:', section)

    students = course.get_users(enrollment_type='student', enrollment_state='active', include=['enrollments'])
    print("kuid,name")
    for student in students:
        if (student.enrollments[0]["course_section_id"] == section.id):
            print('%6s,' % kuid(student.email), student.name)


def print_usage(progname):
    print(f"Usage: ./{progname} COURSE_ID [Option]\n\tOptions:\n\t--help\t\t\t: Print this message\n\t--ids\t\t\t: Print kuids and names for a sections\n\t--get-ass-dist FNAME\t: Select an assignment and construct a distribution between available\n\t\t\t\t  TA's, resulting in a YAML-file suitable for using with\n\t\t\t\t  the --select-ta flag in staffeli/download.py.\n\t\t\t\t  The result will be written to FNAME.")


def get_course(course_id):
    return Canvas(API_URL, API_KEY).get_course(course_id)


def exit_error(errmsg):
    print(errmsg)
    print_usage(sys.argv[0])
    sys.exit(1)

if __name__ == '__main__':
    argc = len(sys.argv)
    # Parse arguments
    if (argc < 3 or "--help" in sys.argv):
        print_usage(sys.argv[0])
        sys.exit(0)
    # Assume course_id is the first arg
    course_id = sys.argv[1]
    # Assume the canvas token is in home, named exactly '.canvas.token'
    path_token = os.path.join(
        str(Path.home()),
        '.canvas.token'
    )


    API_URL = 'https://absalon.ku.dk/'
    with open(path_token, 'r') as f:
        API_KEY = f.read().strip()

    canvas = Canvas(API_URL, API_KEY)
    try:
        course = canvas.get_course(course_id)
    except:
        exit_error("Failed to parse course id.")

    if ("--get-ass-dist" in sys.argv):
        idx = sys.argv.index("--get-ass-dist")
        try:
            fname = sys.argv[idx+1]
        except:
            exit_error("Failed to find output filename")
        course = get_course(course_id)
        create_and_write_assignment_distribution(course, fname)

    elif ("--ids" in sys.argv):
        course = get_course(course_id)
        get_section_info(course)

    else:
        exit_error("Non-valid arguments.")


