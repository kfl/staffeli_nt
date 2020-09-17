#!/usr/bin/env python3

import os
import sys
#import glob
import shutil
#import zipfile
import hashlib
#from zipfile import BadZipFile
from pathlib import Path

from vas import *
from util import *

def digest(data):
    return hashlib.sha256(data).digest()

def kuid(login_id):
    return login_id.split('@', maxsplit=1)[0]

if __name__ == '__main__':
    course_id = sys.argv[1]
    path_token = os.path.join(
        str(Path.home()),
        '.canvas.token'
    )

    API_URL = 'https://absalon.ku.dk/'
    with open(path_token, 'r') as f:
        API_KEY = f.read().strip()

    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(course_id)

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
