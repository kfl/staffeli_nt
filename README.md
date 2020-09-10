# staffeli_nt

Staffeli NT Technology


Getting Started
===============

With Staffeli, we work with local course clones. We aim to keep these
clones compatible with git.

We recommend that you create a local directory ``canvas``,
``absalon``, or similar, for all of you Canvas-related local course
clones. Staffeli needs some initial help to be able to login with your
credentials. You need to [generate a
token](https://guides.instructure.com/m/4214/l/40399-how-do-i-obtain-an-api-access-token-for-an-account>]
for Staffeli to use, and save it as ``.token``, ``token``, or
``token.txt`` in this high-level directory.

**NB!** This is your personal token so **do not** share it with others,
else they can easily impersonate you using a tool like Staffeli.
Unfortunately, to the best of our knowledge, Canvas has no means to
segregate or specialize tokens, so this is really "all or nothing".



Fetch Submissions for an Assignment
-----------------------------------

Use `download.py <template.yaml> <assignment-dir>`. For instance, to fetch all submissions for "ass1":

    $ ./download.py ass1-template.yml ass1
