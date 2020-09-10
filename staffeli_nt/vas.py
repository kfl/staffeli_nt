import collections

from canvasapi import Canvas
from ruamel.yaml import YAML

yaml = YAML()
yaml.indent(mapping=4, sequence=6, offset=3)
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
    tasks: [Task]
    total_points: int

    def __init__(self, name: str, tasks: [Task]):
        self.name = name
        self.tasks = tasks
        self.total_points = 0
        for task in self.tasks:
            self.total_points += task.points

    def format_md(self, sheet):
        assert isinstance(sheet, GradingSheet)
        assert sheet.is_graded(self), 'can only format graded'

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
            form += '\n'

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

class MetaAssignment:
    id: int
    name: str

    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    def serialize(self):
        return {
            'assignment': collections.OrderedDict([
                ('id', self.id),
                ('name', self.name)
            ])
        }

class Meta:
    def __init__(self, course: MetaCourse, assignment: MetaAssignment):
        self.course = course
        self.assignment = assignment

    def serialize(self):
        ser = self.course.serialize()
        ser.update(self.assignment.serialize())
        return ser

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

        if isinstance(grade, int) or isinstance(grade, float):
            assert grade <= points, 'too many points given %s/%s' % (grade, points)

    def serialize(self):

        inner = [
            ('grade', self.grade),
            ('feedback', self.feedback)
        ]

        if self.points is not None:
            inner.append(('points', self.points))

        if self.bonus is not None:
            inner.append(('bonus', self.bonus))

        inner = sorted(inner, key=lambda x: (len(x[0]), x[0]))

        return {self.name: collections.OrderedDict(inner)}

    def get_grade(self, task: Task, with_bonus=True):
        bonus = 0 if (self.bonus is None) or (not with_bonus) else self.bonus

        if self.grade is not None:
            return self.grade + bonus

        if task.default is not None:
            return task.default + bonus

        return None

    def is_graded(self, task: Task):
        return self.get_grade(task) is not None

class GradingSheet:
    name : str
    students: [Student]

    def __init__(self, name: str, solutions: [Solution], students: [Student]):
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
                grade = v['grade'],
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
        name=struct['assignment']['name']
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
        tasks = tasks
    )
