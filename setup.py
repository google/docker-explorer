#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Installation and deployment script."""

from setuptools import find_packages
from setuptools import setup
from docker_explorer import __version__ as de_version


de_description = 'Docker forensic analysis tool.'

de_long_description = (
    'docker-explorer is a tool to help forensic analysis of offline Docker '
    'installations')

setup(
    name='docker_explorer',
    version=de_version,
    description=de_description,
    long_description=de_long_description,
    url='https://github.com/google/docker-explorer',
    author='Docker-Explorer devs',
    license='Apache License, Version 2.0',
    packages=find_packages(exclude=['tests', 'tools']),
    install_requires=[
        'requests',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    scripts=[
        'tools/de.py',
        'tools/merge_vhdx.py'],
    test_suite='tests'
)
