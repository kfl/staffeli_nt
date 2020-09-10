import os
import sys

from pathlib import Path

from vas import *

NAME_SHEET = 'grade.yml'

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
LIGHT_PURPLE = '\033[94m'
PURPLE = '\033[95m'
END = '\033[0m'

if __name__ == '__main__':

    path_template = sys.argv[1]
    path_submissions = sys.argv[2]

    sheets = []

    with open(path_template, 'r') as f:
        tmpl = parse_template(f.read())

    # fetch every grading sheet
    for root, dirs, files in os.walk(path_submissions):
        for name in files:
            if name != NAME_SHEET:
                continue

            path = os.path.join(root, name)
            #print(path)
            with open(path, 'r') as f:
                sheets.append((
                    path,
                    parse_sheet(f.read())
                    ))

    # check that every sheet is complete
    graded = True
    missing = 0
    done = 0
    for (path, sheet) in sheets:
        if not sheet.is_graded(tmpl):
            print(f'{RED}█{END} {path} is not graded')
            graded = False
            missing += 1
        else:
            total = sheet.get_grade(tmpl)
            tp = tmpl.total_points
            print(f"{GREEN}█{END} {total}/{tp} points for {path}")
            done += 1

    if graded is False:
        print(f'Grading is not complete, {done} done, {missing} missing')
    else:
        print("Yay, time to upload")
