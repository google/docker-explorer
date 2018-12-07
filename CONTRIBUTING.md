# How to Contribute

We'd love to accept your patches and contributions to this project. There are
just a few small guidelines you need to follow.

## Contributor License Agreement

Contributions to this project must be accompanied by a Contributor License
Agreement. You (or your employer) retain the copyright to your contribution,
this simply gives us permission to use and redistribute your contributions as
part of the project. Head over to <https://cla.developers.google.com/> to see
your current agreements on file or to sign a new one.

You generally only need to submit a CLA once, so if you've already submitted one
(even if it was for a different project), you probably don't need to do it
again.

## Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://help.github.com/articles/about-pull-requests/) for more
information on using pull requests.

Before submitting a pull request for review, please make sure that your code
follows the Style Guide, has proper tests implemented, and that they pass
successfully.

```
$ python ./tests.py
```

## Style guide

We primarily follow the Google Python Style Guide. Some variations are:

* Quote strings as ' or """ instead of "
* Textual strings should be Unicode strings so please include
`from __future__ import unicode_literals` in new python files.
* Use the format() function instead of the %-way of formatting strings.
* Use positional or parameter format specifiers with typing e.g. '{0:s}' or
  '{text:s}' instead of '{0}', '{}' or '{:s}'. If we ever want to have
  language specific output strings we don't need to change the entire
  codebase. It also makes is easier in determining what type every parameter
  is expected to be.
* Use "cls" as the name of the class variable in preference of "klass"
* When catching exceptions use "as exception:" not some alternative form like
  "as error:" or "as details:"
* Use textual pylint overrides e.g. "# pylint: disable=no-self-argument"
  instead of "# pylint: disable=E0213". For a list of overrides see:
  http://docs.pylint.org/features.html

## Community Guidelines

This project follows [Google's Open Source Community
Guidelines](https://opensource.google.com/conduct/).
