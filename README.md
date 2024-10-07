[![PyPI version](https://badge.fury.io/py/betterpathlib.svg)](https://badge.fury.io/py/betterpathlib)
[![ReadTheDocs](https://readthedocs.org/projects/betterpathlib/badge/?version=latest)](https://readthedocs.org/projects/betterpathlib)

# betterpathlib
An Path library that is an extension to Pythons built-in pathlib.Path.

```
pip install betterpathlib[all]
```

Especially useful for dealing with: 
- paths with multiple suffixes, e.g. files of the sort `archive.tar.gz`.
- paths with numerical suffixes, i.e. files of the sort `part.rar.001`.

... and in addition, adds methods for:
- Case-insensitive globbing
- Copying files and directories
- Reading JSON directly from Path object
- Downloading file from URL to destination, if the file is not already downloaded
- Atomic writes
- Random paths (with optional prefix and/or suffix)

Has no external dependencies if not installed with optional features.


## Optional features
- `download` - Requires `requests` and and allows for `or_download()`
- `similarpaths` - Requires `thefuzz` and and allows for `most_similar_paths()`


