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

import os
import bsdiff4
import stat
import shutil
import tarfile
import filecmp

from hashlib import sha1
from tempfile import mkstemp
from StringIO import StringIO

__all__ = ['PDEntry', 'NEW_FILE_HASH']

NEW_FILE_HASH=sha1('').hexdigest()

ENTRY_HEADER_DEST_HASH = 'pdar_entry_dest_hash'
ENTRY_HEADER_ORIG_HASH = 'pdar_entry_orig_hash'
ENTRY_HEADER_TARGET = 'pdar_entry_target'

class PDEntry(object):

    def __init__(self, target, orig_data, dest_data, mode=None,
                 orig_hash=None, dest_hash=None, delta=None):
        if mode is None:
            default_mode = os.umask(0)
            os.umask(default_mode)
            mode = default_mode
        self._mode = mode
        if target is not None and orig_data is not None \
                and dest_data is not None and delta is None:
            self._target = target
            self._orig_hash = sha1(orig_data).hexdigest()
            self._dest_hash = sha1(dest_data).hexdigest()
            self._delta = bsdiff4.diff(orig_data, dest_data)

        elif target is not None and delta is not None \
                and orig_hash is not None and dest_hash is not None:
            self._target = target
            self._orig_hash = orig_hash
            self._dest_hash = dest_hash
            self._delta = delta
        else:
            raise RuntimeError(
                "You must pass either 'orig_data' and 'dest_data' OR "
                "'delta', 'orig_hash', and 'dest_hash'")

    @property
    def mode(self):
        return self._mode

    @property
    def delta(self):
        return self._delta

    @property
    def isnewfile(self):
        return self.orig_hash == NEW_FILE_HASH

    @property
    def target(self):
        return self._target

    @property
    def orig_hash(self):
        return self._orig_hash

    @property
    def dest_hash(self):
        return self._dest_hash

    def _verify_hash(self, digest, data=None, path=None):
        if data is None:
            if path is None:
                path = self.target
            with open(path, 'rb') as verify_reader:
                data = verify_reader.read()
        return digest == sha1(data).hexdigest()

    def verify_orig_hash(self, data=None, path=None):
        if self.isnewfile:
            if data:
                return False

            if path is None:
                path = self.target
            if os.path.exists(path):
                return False

        return self._verify_hash(self.orig_hash, data, path)

    def verify_dest_hash(self, data=None, path=None):
        return self._verify_hash(self.dest_hash, data, path)

    def patch(self, path=None, data=None, patcher=None):
        if path is None:
            path = self.target
        if data is None:
            if self.isnewfile and not os.path.exists(path):
                data = ''
            elif os.path.exists(path):
                with open(path, 'rb') as data_reader:
                    data = data_reader.read()
        patcher.apply_entry(self, path, data)

    def pax_dump(self, tfile):
        buf = StringIO(self.delta)
        buf.seek(0)
        info = tarfile.TarInfo(
            name=os.path.join(
                self.target, self.orig_hash))
        info.pax_headers.update({
                ENTRY_HEADER_TARGET: unicode(self.target),
                ENTRY_HEADER_ORIG_HASH: unicode(self.orig_hash),
                ENTRY_HEADER_DEST_HASH: unicode(self.dest_hash)})
        info.size = len(buf.buf)
        info.mode = self.mode
        tfile.addfile(tarinfo=info, fileobj=buf)

    @classmethod
    def pax_load(cls, tfile, tinfo):
        headers = tinfo.pax_headers
        return cls(target=headers[ENTRY_HEADER_TARGET],
                   orig_data=None, dest_data=None,
                   delta=tfile.extractfile(tinfo).read(),
                   orig_hash=headers[ENTRY_HEADER_ORIG_HASH],
                   dest_hash=headers[ENTRY_HEADER_DEST_HASH],
                   mode=tinfo.mode)

    @classmethod
    def create(cls, target, orig, dest):
        needs_patch = False
        if not os.path.exists(orig):
            needs_patch = True
            orig_data = ''
        elif not filecmp.cmp(orig, dest, False):
            needs_patch = True
            with open(orig, 'rb') as orig_reader:
                orig_data = orig_reader.read()

        if needs_patch:
            with open(dest, 'rb') as dest_reader:
                return cls(
                    target, orig_data, dest_reader.read(),
                    stat.S_IMODE(os.stat(dest).st_mode))
        return None
