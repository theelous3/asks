#!/usr/bin/env python3

from setuptools import setup
from sys import version_info

if version_info < (3, 5, 2):
    # 3.5.2 is when __aiter__ became a synchronous function
    raise SystemExit('Sorry! asks requires python 3.5.2 or later.')

setup(
    name='asks',
    description='asks - async http',
    long_description='asks is an async http lib for curio and trio',
    license='MIT',
    version='1.5.13',
    author='Mark Jameson - aka theelous3',
    url='https://github.com/theelous3/asks',
    packages=['asks'],
    install_requires=['h11', 'async_generator', 'multio>=0.2.3'],
    tests_require=['pytest', 'curio', 'trio'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Framework :: Trio',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
