#!/usr/bin/env python

# This file is part of pdar.
#
# Copyright 2011 Jason Penney
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""setup.py for pdar"""

from setuptools import setup, find_packages
import os
import sys
import imp
import re

_pkgname = 'pdar'

def get_meta(pkgname, path='.'):
    '''Try to extract metadata fields (__version__, __author__, etc.)
    from a package without importing it'''

    pkgfile, pathname, description = imp.find_module(pkgname)
    if not pkgfile and os.path.isdir(pathname):
        initfile = os.path.join(pathname, '__init__.py')
        if os.path.exists(initfile):
            pkgfile = open(initfile)

    meta = dict()
    if pkgfile:
        match = False
        tripple = False
        matchlines = []
        for line in pkgfile:
            line = line.strip(os.linesep)
            if (line.startswith('__') and '=' in line) \
                   or (match and line.startswith(' ')) \
                   or tripple:
                if line.strip().endswith("'''"):
                    if tripple:
                        line += '.strip(os.linesep)'
                    match = False
                    tripple = not tripple
                matchlines.append(line)

            else:
                match = False
        code_re = re.compile(r'^(__[^ ]+__)', flags=re.M|re.S)
        code = code_re.sub(r"meta['\1']",
                           os.linesep.join(matchlines))
        try:
            exec(code)
        except Exception, err:
            sys.stderr.write("error parsing metadata from '%s'"
                             % pkgname)
        
    return meta

extra = {}
if sys.version_info >= (3,):
    extra['use_2to3'] = True

meta = get_meta(_pkgname)

setup(
    name=_pkgname,
    version=meta.get('__version__', 'unknown'),
    author=meta.get('__author__', 'Jason Penney'),
    author_email=meta.get('__email__','jpenney@jczorkmid.net'),
    url=meta.get('__url__','http://jasonpenney.net/'),
    maintainer=meta.get('__maintainer__', 'Jason Penney'),
    maintainer_email=meta.get('__maintainer_email__',
                              meta.get('__email__',
                                       'jpenney@jczorkmid.net')),
    description=meta.get('__description__', None),
    long_description=meta.get('__long_description__', None),
    download_url=meta.get('__download_url__', None),
    license=meta.get('__license__', None),
    packages=find_packages(exclude=['tests']),
    install_requires='''
    bsdiff4 >= 1.0.1
    argparse
    ''',
    test_suite='unittest2.collector',
    tests_require='''
    unittest2
    ''',
    entry_points="""
    [console_scripts]
    pdar = pdar.console:pdar_cmd
    """,
    include_package_data=True,
    exclude_package_data={'': ['tests/*']},
    **extra
    )