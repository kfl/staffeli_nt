# staffeli_nt

Staffeli NT Technology


Getting Started
===============

With Staffeli, we work with local course clones. We aim to keep these
clones compatible with git.

We recommend that you create a local directory ``canvas``,
``absalon``, or similar, for all of you Canvas-related local course
clones.

Obtain your personal Canvas token
---------------------------------
Staffeli needs some initial help to be able to login with your
credentials. You need to [generate a
token](https://guides.instructure.com/m/4214/l/40399-how-do-i-obtain-an-api-access-token-for-an-account)
for Staffeli to use, and save it in your home directory in a file with
the name `.canvas.token`.

**NB!** This is your personal token so **do not** share it with others,
else they can easily impersonate you using a tool like Staffeli.
Unfortunately, to the best of our knowledge, Canvas has no means to
segregate or specialize tokens, so this is really "all or nothing".

Install required libraries
--------------------------

    $ pip3 install -r requirements.txt

Or you can install in a [virtual
environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/#creating-a-virtual-environment):

 1. Create a virtual environment called `env`.

    On macOS and Linux:

        $ python3 -m venv env

    On Windows:

        $ py -m venv env

 2. Activate `env`

    On macOS and Linux:

        $ source env/bin/activate

    On Windows:

        $ .\env\Scripts\activate

 3. Now install the requirements for `staffeli_nt` in `env`

        $ pip3 install -r requirements.txt




Fetch Submissions for an Assignment
-----------------------------------
There are multiple options for fetching submissions.

The general command is `<staffeli_nt_path>/download.py <course_id> <template.yaml> <assignment-dir> [flags]`, where
- `<staffeli_nt_path>` is the path to the directory where `staffeli_nt` is located, i.e. where the files `download.py` and `upload.py` etc. can be found.
- `<course_id>` is the canvas `course_id` for the course.
- `<template.yaml>` is the template file to use when generating the `grade.yml` file for each submission
- `<assignment_dir>` is a *non-existing* directory, that staffeli will create and store the submissions in.

**Windows**:  
Since `staffeli_nt` is written in `python3`, you will need to invoke it via your `python3` interpreter. 
Example: `python <staffeli_nt_path>/download.py <course_id> <template.yml> <assignment-dir> [flags]`

**Fetching all submissions**:  
To fetch **all** submissions from the course with id `12345`, using the template-file `ass1-template.yml` and create a new directory "ass1dir" to store the submissions in:

    $ <staffeli_nt_path>/download.py 12345 ass1-template.yml ass1dir

This will present you with a list of assignments for the course, where you will interactively choose which assignment to fetch.
For each submission, a directory will be created in `<assignment_dir>`, in which the handed-in files of the submission will be stored, alongside a file `grade.yml` generated form the `<template.yml>` for a TA to fill out during grading of the assignment.
Submission comments, if any, will be downloaded as well, and stored alongside `grade.yml` and the files of the hand-in.

*In case the student hands in a file called `grade.yml` it will be overwritten by staffeli. If the student hands in a file called `submission_comments.txt` and has written submission comments on the submission, the downloaded submission comments will be renamed.*

### Flags
#### Fetching all submissions for a section
What we call "Hold", canvas/absalon calls sections.
To fetch all submissions for an assignment, where the student belongs to a given section, and the `<course_id>` is `12345`:

    $ <staffeli_nt_path>/download.py 12345 ass1-template.yml ass1dir --select-section

This will present you with a list of assignments for the course, where you will interactively choose which assignment to fetch, followed by a list of sections for you to choose from.

#### Fetching specific submissions (based on kuid)
It is possible to fetch specific submissions based on a list of kuids.
To do this, create a YAML-file with the following format:

``` yaml
TA1:
- kuid1
- kuid2
- kuid3
TA2:
- kuid4
- kuid5
```

To then fetch all submissions for an assignment for a given TA:

    $ <staffeli_nt_path>/download.py <course_id> ass1-template.yml ass1dir --select-ta ta_list.yml

where `ta_list.yml` is a YAML-file following the above format.


This will present you with a list of assignments for the course, where you will interactively choose which assignment to fetch, followed by the list of TA's from your `ta_list.yml` file.
Selecting a TA, will fetch submissions from each `kuid` in the file, associated with the chosen TA, i.e. selecting `TA1` will fetch submission from `kuid1`, `kuid2` and `kuid3`.


### Automatically running onlineTA for each submission
In the `template.yml`-file you can add a field:

`onlineTA: https://address.of.onlineTA.dk/grade/assignmentName`

This will (attempt to) run onlineTA for each downloaded submission.


#### Fetching only ungraded submissions (resubs)
It is possile to only fetch submissions that are either ungraded or have a score < 1.0.
Currently this is implemented specifically for the PoP-course and might not be available in the current form in later releases. 
This can be achieved by appending the `--resub` flag to any use of the `download.py`-script.



Upload Feedback and grades
--------------------------

Use `upload.py <template.yaml> <assignment-dir> [--live] [--step]`.
The default to do a *dry run*, that is **not** to upload anything
unless the `--live` flag is given.

For instance, to review all feedback for submissions in the directory
`ass1` before uploading:

    $ <staffeli_nt_path>/upload.py ass1-template.yml ass1 --step


To upload all feedback for submissions in the directory
`ass1`:

    $ <staffeli_nt_path>/upload.py ass1-template.yml ass1 --live

To upload feedback for a single submission:

    $ upload_single.py <POINTS> <meta.yml> <grade.yml> <feedback.txt> [--live]


To generate `feedback.txt` locally for submissions in the directory `ass1`:

    $ <staffeli_nt_path>/upload.py ass1-template.yml ass1 --write-local


Template format
---------------

A (minimal) template could look like:

```yaml
name: Mini assignment

tasks:
  - overall:
      title: Overall
      points: 6
      rubric: |
        Some default feedback.

        Your code and report are unreadable.

        Wow, that's really clever.
```

### Optional fields

The template files support a few optional fields.

- `passing-points: N`:
Adding this field will have the effect, that the grade posted is `1` if the total sum of points is
greater than or equal to `passing-points`, and `0` otherwise.
- `show-points: BOOL`
Setting show-points to `false` will exclude the `points/grade` from the generated `feedback.txt` files.
Use this, if you do not want the students to see the points-per-task, but only receive an overall grade.

- `onlineTA: ADDR`
Include this field to (attempt to) run onlineTA at address `ADDR` for each submission, when downloading submissions.


### Fully fledged example template
```yaml
name: Mega assignment
passing-points: 42
show-points: false
onlineTA: https://yeah-this-is-not-a-real-address.dk/grade/megaassignment

tasks:
  - megaAssignmentGeneral:
      title: Mega assignment - General comments and adherence to hand-in format requirements
      points: 100
      rubric: |
        [*] You should spell check your assignments before handing them in
        [-] You are using the charset iso-8859-1. Please move to the modern age.
        [-] Your zip-file contains a lot of junk. Please be aware of what you hand in.

  - megaAssignmentTask1:
      title: Task 1
      points: 2
      rubric: |
        [+] Your implementation follows the API
        [-] Your implementation does not follow the API
        [+] Your tests are brilliant
        [-] Your tests are not tests, just print-statements.
            This is equivalent to an exam without an examinator, where you shout
            in a room for half an hour and give yourself the grade 12.

  - megaAssignmentTask2:
      title: Task 2
      points: 2
      rubric: |
        [+] Very good points.
        [+] Very good points. However, I disagree with ...
        [-] I fail to comprehend you answer to this task.

  - megaAssignmentBonusTask:
      title: Bonus tasks that do not give points, or another option for general comments
      rubric: |
        [*] You did extra work! It won't help you though.
```
