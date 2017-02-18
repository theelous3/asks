#!/usr/bin/env python3

from setuptools import setup

setup(
    name='asks',
    description='asks - async http',
    long_description='asks is an async http lib',
    license='MIT',
    version='0.0.2',
    author='Mark Jameson - aka theelous3',
    url='https://github.com/theelous3/asks',
    packages=['asks'],
    install_requires=['curio'],
    classifiers=['Programming Language :: Python :: 3']
)
