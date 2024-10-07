[![PyPI version](https://badge.fury.io/py/betterpathlib.svg)](https://badge.fury.io/py/betterpathlib)
[![ReadTheDocs](https://readthedocs.org/projects/betterpathlib/badge/?version=latest)](https://readthedocs.org/projects/betterpathlib)

# betterpathlib
An Path library that is an extension to Pythons built-in pathlib.Path.

```
pip install betterpathlib[all]
```

Especially useful for dealing with numerical suffixes, i.e. files of the sort `myfile.rar.001`.

Has no external dependencies if not installed with optional features.


## Optional features
`download` - Requires `requests` and and allows for `or_download()`
`similarpaths` - Requires `thefuzz` and and allows for `most_similar_paths()`


