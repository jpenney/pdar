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

import argparse
import pdar
import pdar.errors
import os
import logging
import locale
import shutil

def pdar_create(args):
    archive = pdar.PDArchive(orig_path=args.path1, 
                             dest_path=args.path2, 
                             patterns=args.patterns)
    if args.backup:
        if os.path.exists(args.archive_name):
            backup_name = '.'.join([args.archive_name, 'bak'])
            logging.debug("creating backup of '%s' -> '%s'" % (
                    args.archive_name, backup_name))
            args.force = True
            shutil.copy(args.archive_name, 
                        '.'.join([args.archive_name, 'bak']))
    logging.debug("saving archive: %s" % args.archive_name)
    archive.save(args.archive_name, args.force)
    logging.debug("Success!")
    return 0
    
def pdar_apply(args):
    archive = pdar.PDArchive.load(args.archive_name)
    if args.output_path:
        logging.debug("copying files '%s'->'%s'", args.path,
                      args.output_path)
        shutil.copytree(args.path, args.output_path)
        path = args.output_path
    else:
        path = args.path

    archive.patch(path)
    return 0

    
         

def pdar_info(args):
    _pdar_info_header = '''\
PDAR archive: %(archive_name)s
PDAR version: %(pdar_version)s
     created: %(created)s
        size: %(archive_size)s bytes
'''
    archive_size = os.path.getsize(args.archive_name)
    archive = pdar.PDArchive.load(args.archive_name)

    entry_info = [
        (locale.format("%d", len(entry.delta), grouping=True),
         entry.target) for entry in archive.patches]

    max_size_str_width = max(len(info[0]) for info in entry_info)
    max_target_str_width = max(len(info[1]) for info in entry_info)

    _pdar_entry_line_format = '  %s%ds  %ss' % (
        '%(size)', max_size_str_width, '%(target)'
        )
        
    print _pdar_info_header % {
        'archive_name': args.archive_name,
        'pdar_version': archive.pdar_version,
        'created': str(archive.created_datetime),
        'archive_size': locale.format("%d", archive_size, grouping=True)}

    print _pdar_entry_line_format % {
        'size': 'size',
        'target': 'target'}

    print _pdar_entry_line_format % {
        'size': '-' * max_size_str_width,
        'target': '-' * max_target_str_width }

    for entry in entry_info:
        print _pdar_entry_line_format % {
            'size': entry[0],
            'target': entry[1]}
    
    return 0
        


def pdar_cmd():

    if locale.getlocale() == (None, None):
        locale.setlocale(locale.LC_ALL,'')

    parser = argparse.ArgumentParser(
        description='utility for manipulating portable delta archives')
    parser.add_argument('-V', '--version', action='version',
                        version='%(prog)s ' + pdar.__version__,
                        help='show version message and exit')

    logging_args = parser.add_mutually_exclusive_group()
    logging_args.add_argument('-d', '--debug', dest='log_level',
                              action='store_const', const=logging.DEBUG,
                              default=logging.INFO)
    logging_args.add_argument('-q', '--quiet', dest='log_level',
                              action='store_const', const=logging.WARN,
                              default=logging.INFO)
    subparsers = parser.add_subparsers(
        title='commands',
        )

    parser_create = subparsers.add_parser(
        'create',
        description='create pdar archive',
        help='create pdar archive')
    parser_create.set_defaults(func=pdar_create)
    parser_create.add_argument(
        '-f', '--force', help='overwrite existing archives',
        dest='force', action='store_true')
    parser_create.add_argument(
        '-b', '--backup', help=(
            'backup existing archive before overwriting '
            '(implies force, existing backups may be lost).'),
        dest='backup', action='store_true')
                        
    parser_create.add_argument(
        'archive_name',
        help='path to output pdar archive')
    parser_create.add_argument(
        'path1',
        help='path to source data')
    parser_create.add_argument(
        'path2',
        help='path to modified data')
    parser_create.add_argument(
        'patterns',
        nargs='*',
        metavar='pattern',
        default=['*'])

    parser_apply = subparsers.add_parser(
        'apply',
        description='apply pdar archive as patch',
        help='apply pdar archive as patch'
        )
    parser_apply.set_defaults(func=pdar_apply)
    parser_apply.add_argument(
        '-o', '--output-path',
        help=('apply patch in alternate location, rather than overwriting '
              'original files'),
        dest='output_path', default=None, type=str)
    parser_apply.add_argument(
        'archive_name',
        help='path to output pdar archive')
    parser_apply.add_argument(
        'path',
        help='path to which pdar will be applied')
    
    parser_info = subparsers.add_parser(
        'info',
        description='show info about pdar archive',
        help='show info about pdar archive')
    parser_info.set_defaults(func=pdar_info)
    parser_info.add_argument(
        'archive_name',
        help='path to output pdar archive')

    args = parser.parse_args()
    
    # configure logging

    logging.basicConfig(format="%(message)s",
                        level=args.log_level)
    
    if args.log_level == logging.DEBUG:
        parser.exit(args.func(args))

    try:
        parser.exit(args.func(args))
    except pdar.errors.InternalError, err:
        logging.error("internal error")
        logging.debug(" -- %s", str(err))
        parser.exit(4)
    except Exception, err:
        logging.error(str(err))
        parser.exit(1)


    
