import tomllib
import os


def get_version():
    pyproject_path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    return pyproject["tool"]["poetry"]["version"]


__version__ = get_version()
