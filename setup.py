#!/usr/bin/env python3

from setuptools import setup
from sys import version_info

ver = version_info[:2]
if ver < (3, 6):
    raise SystemExit('Sorry! asks requires python 3.6.0 or later.')

setup(
    name='asks',
    description='asks - async http',
    long_description='asks is an async http lib for curio and trio',
    license='MIT',
    version='1.2.2',
    author='Mark Jameson - aka theelous3',
    url='https://github.com/theelous3/asks',
    packages=['asks'],
    install_requires=['h11'],
    tests_require=['pytest'],
    classifiers=['Programming Language :: Python :: 3']
)
