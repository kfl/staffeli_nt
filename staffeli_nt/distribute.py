import os
import sys
from math import ceil
from download import kuid, sort_by_name
from pathlib import Path
from canvasapi import Canvas
from typing import Dict, Any

def chunks(l, n):
    # Yield n number of sequential chunks from l.
    d, r = divmod(len(l), n)
    for i in range(n):
        si = (d+1)*(i if i < r else r) + d*(0 if i < r else i - r)
        yield l[si:si+(d+1 if i < r else d)]

def balance_two_lists (l1, l2):
    combined = l1 + l2
    length = len (combined)
    return combined[:(length//2)], combined[(length//2):]

def balance_submissions (l):
    if len(l) < 2:
        return l

    len_list = [ len (elem) for elem in l ]
    min_ind = len_list.index (min (len_list))
    max_ind = len_list.index (max (len_list))
    l1 = l[min_ind]
    l2 = l[max_ind]

    if len (l2) - len (l1) < 2:
        return l
    else:
        l1_balanced, l2_balanced = balance_two_lists (l1, l2)
        l[min_ind] = l1_balanced
        l[max_ind] = l2_balanced
        return balance_submissions (l)


if __name__ == '__main__':
    course_id = sys.argv[1]
    path_destination = sys.argv[2]
    path_token = os.path.join(
        str(Path.home()),
        '.canvas.token'
    )

    balance = '--balance' in sys.argv
    API_URL = 'https://absalon.ku.dk/'

    with open(path_token, 'r') as f:
        API_KEY = f.read().strip()

    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(course_id)

    num_TA = int (input ('\nHow many TAs to distribute between? '))


    possible_distribution_modes = ['Split all', 'By Section']
    print('\nDistribution modes:')
    for n, mode in enumerate (possible_distribution_modes):
        print ('%2d :' % n, mode)
    distribution_mode = possible_distribution_modes [int (input ('Select mode: '))]


    assignments = sort_by_name(course.get_assignments())
    print('\nAssignments:')
    for n, assignment in enumerate(assignments):
        print('%2d :' % n, assignment.name)
    index = int(input('Select assignment: '))
    assignment = assignments[index]


    handins: Dict[str, Any] = {}
    participants = []
    submission_groups = []
    section_names = []

    print ('Getting assignments...')
    if distribution_mode == 'Split all':
        submission_groups = chunks(list (assignment.get_submissions()), num_TA)
    elif distribution_mode == 'By Section':
        # First section seems to always be a general purpose one, so we skip it.
        # It's honestly a stupid hack that probably won't work in general
        sections = sort_by_name(course.get_sections())[1:]
        for index in range (len (sections)):
            section = course.get_section (sections[index],
                                          include=['students', 'enrollments'])
            if section.students is not None:
                section_names.append (sections[index].name)
                s_ids = [s['id'] for s in section.students if all([ e['enrollment_state'] == 'active'
                                                                    for e in s['enrollments']])]
                section_submissions = section.get_multiple_submissions(
                    assignment_ids=[assignment.id],
                    student_ids=s_ids
                )
                section_submissions = [ submission for submission in section_submissions
                                        if hasattr (submission, 'attachments')]
                submission_groups.append (section_submissions)

    if balance:
        submission_groups = balance_submissions (submission_groups)

    distribution = os.path.join (path_destination, f'{assignment.name}_ta_list.yml')
    with open (distribution, 'w') as f:
        for cur_group, submission_group in enumerate (submission_groups):
            if distribution_mode == 'Split all':
                f.write (f'TA {cur_group}:\n')
            elif distribution_mode == 'By Section':
                f.write (f'{section_names[cur_group]}:\n')

            for submission in submission_group:
                if hasattr(submission, 'attachments'):
                    user = course.get_user(submission.user_id)
                    print(f'User {user.name} handed in something')
                    f.write (f'- {kuid (user.login_id)}\n')

            f.write ('\n')
