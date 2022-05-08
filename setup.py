#!/usr/bin/env python3

from setuptools import setup
from sys import version_info

if version_info < (3, 6, 2):
    # AnyIO 2.0 requires v3.6.2
    raise SystemExit('Sorry! asks requires python 3.6.2 or later.')

setup(
    name='asks',
    description='asks - async http',
    long_description='asks is an async http lib for curio, trio and asyncio',
    license='MIT',
    version='3.0.0',
    author='Mark Jameson - aka theelous3',
    url='https://github.com/theelous3/asks',
    packages=['asks'],
    package_data={
        'asks': ['py.typed'],
    },
    python_requires='>= 3.6.2',
    install_requires=['h11', 'async_generator', 'anyio ~= 3.0'],
    tests_require=['pytest', 'curio', 'trio', 'overly'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Framework :: Trio',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
