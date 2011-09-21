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

import fnmatch
import re
import os
import tarfile
import logging
import filecmp

from datetime import datetime
from gzip import GzipFile
from tempfile import SpooledTemporaryFile
from pkg_resources import parse_version

from pdar.errors import *
from pdar.entry import *
from pdar.patcher import DEFAULT_PATCHER_TYPE
from pdar import PDAR_VERSION, DEFAULT_HASH_TYPE

__all__ = ['PDArchive', 'PDAR_MAGIC', 'PDAR_ID']

PDAR_MAGIC = 'PDAR'
PDAR_ID = '%s%03d%c' % (
    PDAR_MAGIC, int(float(PDAR_VERSION)), 0)

ARCHIVE_HEADER_VERSION = 'pdar_version'
ARCHIVE_HEADER_CREATED = 'pdar_created_datetime'
ARCHIVE_HEADER_HASH_TYPE = 'pdar_hash_type'


class PDArchive(object):

    def __init__(self, orig_path, dest_path, patterns=['*'], payload=None,
                 hash_type=DEFAULT_HASH_TYPE):
        self._hash_type = hash_type
        if orig_path and dest_path and patterns and not payload:
            logging.debug("""\
creating new pdar:
  orig_path: %s
  dest_path: %s
  patterns: %s""" % (orig_path, dest_path, str(patterns)))
            self._patches = []
            pattern_re = r'|'.join([
                    fnmatch.translate(pat) for pat in patterns])
            pattern_re = re.compile(pattern_re)

            def target_gen(path):
                for root, dirs, files in os.walk(path):
                    for dest in (
                        os.path.normcase(
                            os.path.join(root, f)) for f in files \
                            if pattern_re.match(f)):
                        yield os.path.relpath(dest, path)

            from pprint import pprint

            orig_targets = set(target_gen(orig_path))
            dest_targets = set(target_gen(dest_path))

            common_targets = [
                (target, target, target) for target in (
                    orig_targets & dest_targets)]
            moved_targets = []
            deleted_targets = []
            new_targets = []
            copied_targets = []

            orig_only = orig_targets - dest_targets
            dest_only = dest_targets - orig_targets

            source_match = {}
            for target in dest_only:
                matched = False
                dest_target_path = os.path.join(dest_path, target)
                for potential_match in orig_targets:
                    if filecmp.cmp(dest_target_path,
                                   os.path.join(orig_path, potential_match)):
                        source_match.setdefault(potential_match, [])
                        source_match[potential_match].append(target)
                        matched = True
                        break
                if not matched:
                    new_targets.append((target, None, target))

            matched = source_match.keys()
            for target in orig_only:
                if target not in matched:
                    deleted_targets.append((target, target, None))

            for source, matches in source_match.iteritems():
                move_match = None

                # does this path still exist in dest
                if source not in dest_targets:
                    move_match = matches[-1]
                    matches = matches[:-1]

                for target in matches:
                    copied_targets.append((target, source, target))
                    
                if move_match:
                    target = move_match
                    moved_targets.append((target, source, target))

            def add_entry(targets, cls):
                args = list(targets)
                args += [ orig_path, dest_path, self.hash_type ]
                entry = cls.create(*args)
                if entry:
                    logging.info("adding '%s' entry for: %s" 
                                 % (entry.type_code, entry.target))
                    self._patches.append(entry)
                else:
                    logging.debug("unchanged file: %s" % target[0])

            for target in copied_targets:
                add_entry(target, PDARCopyEntry)

            for target in moved_targets:
                add_entry(target, PDARMoveEntry)

            for target in common_targets:
                add_entry(target, PDARDiffEntry)

            for target in deleted_targets:
                add_entry(target, PDARDeleteEntry)

            for target in new_targets:
                add_entry(target, PDARNewEntry)

            self._pdar_version = PDAR_VERSION
            self._created_datetime = datetime.utcnow()
        elif payload and not orig_path and not dest_path:
            self._patches = payload['patches']
            self._pdar_version = payload[ARCHIVE_HEADER_VERSION]
            self._created_datetime = payload[ARCHIVE_HEADER_CREATED]
            self._hash_type = payload[ARCHIVE_HEADER_HASH_TYPE]

        else:
            raise InvalidParameterError(
                "You must pass either 'orig_path', 'dest_path', and 'patterns' "
                " OR 'payload'")


    @property
    def hash_type(self):
        return self._hash_type

    @property
    def pdar_version(self):
        return self._pdar_version

    @property
    def created_datetime(self):
        return self._created_datetime

    @property
    def patches(self):
        return self._patches

    def save(self, path, force=False):
        if os.path.exists(path) and not force:
            raise RuntimeError('File already exists: %s' % path)
        with SpooledTemporaryFile() as tmpfile:
            gzfile = GzipFile(mode='wb', fileobj=tmpfile, compresslevel=9)
            try:
                tfile = tarfile.open(
                    mode='w', fileobj=gzfile,
                    format=tarfile.PAX_FORMAT,
                    pax_headers={
                        ARCHIVE_HEADER_VERSION: unicode(self.pdar_version),
                        ARCHIVE_HEADER_CREATED: unicode(
                            self.created_datetime.isoformat()),
                        ARCHIVE_HEADER_HASH_TYPE: unicode(self.hash_type)})
                
                try:
                    for patch in self.patches:
                        patch.pax_dump(tfile)
                finally:
                    tfile.close()
                tmpfile.flush()
            finally:
                gzfile.close()

            tmpfile.flush()
            with open(path, 'wb') as patchfile:
                patchfile.write(PDAR_ID)
                tmpfile.seek(0)
                patchfile.writelines(tmpfile)
                patchfile.write(chr(0))
                patchfile.flush()
                patchfile.close()

    def patch(self, path=None, patcher=None):
        if patcher is None:
            patcher = DEFAULT_PATCHER_TYPE(self, path)

        patcher.apply_archive()

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as patchfile:
            file_id = patchfile.read(len(PDAR_ID))
            if not file_id.startswith(PDAR_MAGIC):
                raise PDArchiveFormatError("Not a pdar file: %s" % (path))
            if file_id != PDAR_ID:
                raise PDArchiveFormatError(
                    "Unsupported pdar version ID '%s': %s"
                    % (file_id[len(PDAR_MAGIC):-1], path))
            patches = []
            payload = {}
            tfile = tarfile.open(mode='r:*', fileobj=patchfile)
            try:
                payload.update(tfile.pax_headers)
                if 'created_datetime' in payload:
                    cdt = payload['created_datetime']
                    if isinstance(cdt, basestring):
                        iso, iso_ms = cdt.split('.', 1)
                        cdt = datetime.strptime(
                            iso.replace("-", ""), "%Y%m%dT%H:%M:%S")
                        if iso_ms:
                            cdt = cdt.replace(microsecond=int(iso_ms))
                    payload['created_datetime'] = cdt

                data = tfile.next()
                while data:
                    patch = PDAREntry.pax_load(tfile, data)
                    patches.append(patch)
                    data = tfile.next()
            finally:
                tfile.close()
            payload['patches'] = patches[:]

            # if 0 > cmp(parse_version(PDAR_VERSION),
            #            parse_version(patch.pdar_version)):
            #     raise RuntimeError(
            #         "File '%s' created with pdar protocal %s. "
            #         "This verion of pdar only supports up to %s."
            #         % (patch.pdar_version, PDAR_VERSION))
            # return patch
            return cls(orig_path=None, dest_path=None, patterns=None,
                       payload=payload)
