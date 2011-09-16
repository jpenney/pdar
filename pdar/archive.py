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

from datetime import datetime
from gzip import GzipFile
from tempfile import SpooledTemporaryFile
from pkg_resources import parse_version

from pdar.errors import *
from pdar.entry import PDEntry
from pdar.patcher import DEFAULT_PATCHER_TYPE
from pdar import PDAR_VERSION

__all__ = ['PDArchive', 'PDAR_MAGIC', 'PDAR_ID']

PDAR_MAGIC = 'PDAR'
PDAR_ID = '%s%03d%c' % (
    PDAR_MAGIC, int(float(PDAR_VERSION)), 0)

ARCHIVE_HEADER_VERSION = 'pdar_version'
ARCHIVE_HEADER_CREATED = 'pdar_created_datetime'

class PDArchive(object):

    def __init__(self, orig_dir, dest_dir, patterns=['*'], payload=None):
        if orig_dir and dest_dir and patterns and not payload:
            logging.debug("""\
creating new pdar:
  orig_dir: %s
  dest_dir: %s
  patterns: %s""" % (orig_dir, dest_dir, str(patterns)))
            self._patches = []
            pattern_re = r'|'.join([
                    fnmatch.translate(pat) for pat in patterns])
            pattern_re = re.compile(pattern_re)

            for root, dirs, files in os.walk(dest_dir):
                for dest in (
                    os.path.normcase(
                        os.path.join(root, f)) for f in files \
                        if pattern_re.match(f)):
                    target = os.path.relpath(dest, dest_dir)
                    orig = os.path.normcase(os.path.join(orig_dir, target))
                    patch_entry = PDEntry.create(target, orig, dest)
                    if patch_entry:
                        logging.info("adding delta for: %s" % target)
                        self._patches.append(patch_entry)
                    else:
                        logging.debug("unchanged file: %s" % target)

            self._pdar_version = PDAR_VERSION
            self._created_datetime = datetime.utcnow()
        elif payload and not orig_dir and not dest_dir:
            self._patches = payload['patches']
            self._pdar_version = payload[ARCHIVE_HEADER_VERSION]
            self._created_datetime = payload[ARCHIVE_HEADER_CREATED]

        else:
            raise InvalidParameterError(
                "You must pass either 'orig_dir', 'dest_dir', and 'patterns' "
                " OR 'payload'")

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
                            self.created_datetime.isoformat())})
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
                    patch = PDEntry.pax_load(tfile, data)
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
            return cls(orig_dir=None, dest_dir=None, patterns=None,
                       payload=payload)
