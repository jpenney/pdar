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

from bz2 import BZ2File
from datetime import datetime
from gzip import GzipFile
from pdar import PDAR_VERSION, DEFAULT_HASH_TYPE
from pdar.entry import *
from pdar.errors import *
from pdar.patcher import DEFAULT_PATCHER_TYPE
from pkg_resources import parse_version
from shutil import rmtree
from tempfile import SpooledTemporaryFile, mkstemp
import filecmp
import fnmatch
import logging
import os
import re
import tarfile

__all__ = ['PDArchive', 'PDAR_MAGIC', 'PDAR_ID']

PDAR_MAGIC = 'PDAR'
PDAR_ID = '%s%03d%c' % (
    PDAR_MAGIC, int(parse_version(PDAR_VERSION)[0]), 0)

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
                for root, dummy, files in os.walk(path):
                    for dest in (
                        os.path.normcase(
                            os.path.join(root, f)) for f in files \
                            if pattern_re.match(f)):
                        yield os.path.relpath(dest, path)

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
                args += [orig_path, dest_path, self.hash_type]
                entry = cls.create(*args)  # pylint: disable=W0142
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
                "You must pass either 'orig_path', 'dest_path', and "
                "'patterns' OR 'payload'")

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
        with open(path, 'wb') as patchfile:
            self.save_archive(patchfile)

    def save_archive(self, patchfile):
        with SpooledTemporaryFile() as tmpfile:
            tfile = tarfile.open(
                mode='w', fileobj=tmpfile,
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

            # find best compression
            archive_path = None
            for comp in [GzipFile, BZ2File]:
                dummy, test_path = mkstemp()
                os.close(dummy)
                compfile = comp(test_path, mode='wb',
                                compresslevel=9)
                tmpfile.seek(0)
                compfile.writelines(tmpfile)
                compfile.close()
                if not archive_path or os.path.getsize(
                    archive_path) > os.path.getsize(test_path):
                    if archive_path and os.path.exists(archive_path):
                        os.unlink(archive_path)
                    archive_path = test_path

            patchfile.write(PDAR_ID)
            with open(archive_path, 'rb') as archive:
                patchfile.writelines(archive)
            patchfile.flush()

    def patch(self, path=None, patcher=None):
        if patcher is None:
            patcher = DEFAULT_PATCHER_TYPE(self, path)

        patcher.apply_archive()

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as patchfile:
            try:
                return cls.load_archive(patchfile)
            except PDArchiveFormatError, err:
                raise PDArchiveFormatError("%s: %s" % (str(err), path))

    @classmethod
    def load_archive(cls, patchfile):
        with SpooledTemporaryFile() as archive:
            file_id = patchfile.read(len(PDAR_ID))
            if not file_id.startswith(PDAR_MAGIC):
                raise PDArchiveFormatError("Not a pdar file")
            if file_id != PDAR_ID:
                raise PDArchiveFormatError(
                    "Unsupported pdar version ID '%s'"
                    % (file_id[len(PDAR_MAGIC):-1]))
            archive.writelines(patchfile)
            archive.seek(0)
            patches = []
            payload = {}
            tfile = tarfile.open(mode='r:*', fileobj=archive)
            try:
                payload.update(tfile.pax_headers)
                if ARCHIVE_HEADER_CREATED in payload:
                    cdt = payload[ARCHIVE_HEADER_CREATED]
                    if isinstance(cdt, basestring):
                        iso, iso_ms = cdt.split('.', 1)
                        cdt = datetime.strptime(
                            iso.replace("-", ""), "%Y%m%dT%H:%M:%S")
                        if iso_ms:
                            cdt = cdt.replace(microsecond=int(iso_ms))
                    payload[ARCHIVE_HEADER_CREATED] = cdt

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
