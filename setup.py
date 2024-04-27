#!/usr/bin/env python

from distutils.core import setup

setup(
    name="betterpath",
    version="1.0",
    author="Torstein Sørnes",
    packages=["betterpath"],
    package_dir={'betterpath':'src'},
    install_requires=[
        "fuzzywuzzy>=0.17.0",
    ],
    zip_safe=False,
)
