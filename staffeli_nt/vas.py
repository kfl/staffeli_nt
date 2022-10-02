import collections

from typing import Optional, List, Tuple
from canvasapi import Canvas # type: ignore
from ruamel.yaml import YAML # type: ignore

yaml = YAML()
yaml.indent(mapping=4, sequence=2, offset=2)
yaml.Representer.add_representer(
    collections.OrderedDict,
    yaml.Representer.represent_dict
)

class Task:
    name: str

    def __init__(self, name: str, title: str, points, default, rubric: str):
        self.name = name
        self.title = title
        self.points = points
        self.default = default
        self.rubric = rubric

        assert self.points is None or float(self.points) >= 0
        assert self.default is None or float(self.default) >= 0

        if self.default and self.points:
            assert 0 <= self.default <= self.points

class Assignment:
    name: str
    tasks: List[Task]
    total_points: int
    passing_points: Optional[int]
    show_points: bool

    def __init__(self, name: str, passing_points: Optional[int], tasks: List[Task],
                 show_points: Optional[bool], onlineTA: Optional[str]):
        self.name = name
        self.tasks = tasks
        self.passing_points = int(passing_points) if passing_points is not None else None
        self.total_points = 0
        self.show_points = bool(show_points) if show_points is not None else True
        self.onlineTA = onlineTA
        for task in self.tasks:
            if task.points is not None:
                self.total_points += task.points

    def format_md(self, sheet):
        assert isinstance(sheet, GradingSheet)
        if not sheet.is_graded(self):
            print('trying to format sheet that is not finished graded')

        solutions = {}
        for solution in sheet.solutions:
            solutions[solution.name] = solution

        assert all([s in [t.name for t in self.tasks] for s in solutions])

        body = ''
        for task in self.tasks:
            if task.name not in solutions:
                continue

            solution = solutions[task.name]

            form = ''
            form += '# %s\n' % task.title

            if sheet.is_graded(self) and self.show_points:
                grade = solution.get_grade(task)

                if solution.bonus:
                    form += '%s / %s points (+%s bonus)' % (
                        grade,
                        solution.points,
                        solution.bonus
                    )
                else:
                    form += '%s / %s points' % (
                        grade,
                        solution.points
                    )

            if solution.feedback is not None:
                feedback = solution.feedback.strip()

                if feedback:
                    form += '\n'
                    form += feedback

            form += '\n'
            form += '\n'

            body += form

        return body.strip()

class MetaCourse:
    id: int
    name: str

    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    def serialize(self):
        return {
            'course': collections.OrderedDict([
                ('id', self.id),
                ('name', self.name)
            ])
        }

    def __repr__(self):
        return str(self.__dict__)

class MetaAssignment:
    id: int
    name: str
    section: Optional[int]

    def __init__(self, id: int, name: str, section: Optional[int]):
        self.id = id
        self.name = name
        self.section = section

    def serialize(self):
        return {
            'assignment': collections.OrderedDict([
                ('id', self.id),
                ('name', self.name)
            ] + [ ('section', s) for s in [self.section] if s is not None ])
        }

    def __repr__(self):
        return str(self.__dict__)


class Meta:
    def __init__(self, course: MetaCourse, assignment: MetaAssignment):
        self.course = course
        self.assignment = assignment

    def serialize(self):
        ser = self.course.serialize()
        ser.update(self.assignment.serialize())
        return ser

    def __repr__(self):
        return str(self.__dict__)


class Student:
    id: int
    name: str
    login: str

    def __init__(self, id: int, name: str, login: str):
        self.id = id
        self.name = name
        self.login = login

    def serialize(self):
        return {
            self.id : collections.OrderedDict([
                ('name', self.name),
                ('login', self.login)
            ])
        }

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        if not isinstance(other, Student):
            return False
        return self.id == other.id

class Solution:
    grade: float
    points: float

    def __init__(self, name: str, grade, points, feedback: str='', bonus=None):
        self.name = name
        self.grade = grade
        self.bonus = bonus
        self.points = points
        self.feedback = feedback

        if isinstance(grade, (int, float)):
            assert grade <= points, 'too many points given %s/%s' % (grade, points)

    def serialize(self):

        inner = [ ('feedback', self.feedback) ]

        if self.points is not None:
            inner.extend((('grade', self.grade),
                          ('points', self.points)))

        if self.bonus is not None:
            inner.append(('bonus', self.bonus))

        inner = sorted(inner, key=lambda x: (len(x[0]), x[0]))

        return {self.name: collections.OrderedDict(inner)}

    def get_grade(self, task: Task, with_bonus=True):
        bonus = 0 if (self.bonus is None) or (not with_bonus) else self.bonus

        if self.points is None:
            return 0

        if self.grade is not None:
            return self.grade + bonus

        if task.default is not None:
            return task.default + bonus

        return None

    def is_graded(self, task: Task):
        return self.get_grade(task) is not None

class GradingSheet:
    name : str
    students: List[Student]

    def __init__(self, name: str, solutions: List[Solution], students: List[Student]):
        self.name = name
        self.students = students
        self.solutions = solutions

    def serialize(self):
        return collections.OrderedDict([
            ('name', self.name),
            ('students', [s.serialize() for s in self.students]),
            ('solutions', [s.serialize() for s in self.solutions])
        ])

    def total(self):
        total = 0

        for solution in self.solutions:
            total += solution.grade
            if solution.bonus is not None:
                total += solution.bonus

        return total

    def get_grade(self, ass: Assignment):
        total = 0
        tasks = {task.name: task for task in ass.tasks}
        for sol in self.solutions:
            task = tasks[sol.name]
            try:
                total += sol.get_grade(task)
            except TypeError:
                return None
        if ass.passing_points is not None:
            return 1 if total >= ass.passing_points else 0
        return total

    def is_graded(self, ass: Assignment):
        return self.get_grade(ass) is not None

def parse_sheet(data):
    def flat(comseq):
        return sum([list(s.items()) for s in comseq], [])

    struct = yaml.load(data)

    assert len(struct) == 3, 'fields: name, students, solutions'

    return GradingSheet(
        struct['name'],
        students=[
            Student(
                id = k,
                name = v['name'],
                login = v['login']
            )
            for (k, v) in flat(struct['students'])
        ],
        solutions=[
            Solution(
                name = k,
                bonus = v['bonus'] if 'bonus' in v else None,
                points = v['points'] if 'points' in v else None,
                grade = v['grade'] if 'points' in v else None,
                feedback = v['feedback']  if 'feedback' in v else None
            )
            for (k, v) in flat(struct['solutions'])
        ]
    )

def create_student(student):
    return Student(
        id=student.id,
        name=student.name,
        login=student.login_id
    )

def create_solution(task):
    return Solution(
        name = task.name,
        bonus = None,
        grade = None,        # unassigned
        points = task.points, # maximum points
        feedback = task.rubric
    )

def create_sheet(template, students):
    solutions = []
    return GradingSheet(
        name=template.name,
        solutions=[create_solution(t) for t in template.tasks],
        students=[create_student(s) for s in students]
    )

def parse_meta(data):
    struct = yaml.load(data)

    course = MetaCourse(
        id=struct['course']['id'],
        name=struct['course']['name']
    )

    assignment = MetaAssignment(
        id=struct['assignment']['id'],
        name=struct['assignment']['name'],
        section=struct['assignment'].get('section')
    )

    return Meta(course, assignment)

def parse_template(data):
    struct = yaml.load(data)
    tasks = []
    for t in struct['tasks']:
        [name] = t.keys()
        tasks.append(
            Task(
                name=name,
                title=t[name]['title'],
                points=t[name]['points'] if 'points' in t[name] else None, # max points
                default=t[name]['default'] if 'default' in t[name] else None, # default points
                rubric=t[name]['rubric'] if 'rubric' in t[name] else None # default feedback
            )
        )
        # TODO warn about spurious fields

    return Assignment(
        name = struct['name'],
        passing_points = struct.get('passing-points'),
        tasks = tasks,
        show_points = struct.get('show-points'),
        onlineTA = struct.get('onlineTA')
    )

def parse_students_and_tas(data) -> Tuple[List[str], List[List[str]]]:
    struct = yaml.load(data)
    tas = []
    stud : List[List[str]] = []
    for t, students in struct.items():
        tas.append(t)
        stud.append(list(filter(None,students)))
    return tas, stud
