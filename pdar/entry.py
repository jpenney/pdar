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
import tarfile
import filecmp

from pdar import DEFAULT_HASH_TYPE
import hashlib
from StringIO import StringIO


__all__ = ['PDAREntry', 'PDARCopyEntry', 'PDARNewEntry',
           'PDARMoveEntry', 'PDARDeleteEntry', 'PDARDiffEntry' ]

ENTRY_HEADER_TYPE = 'pdar_entry_type'
ENTRY_HEADER_DEST_DIGEST = 'pdar_entry_dest_digest'
ENTRY_HEADER_ORIG_DIGEST = 'pdar_entry_orig_digest'
ENTRY_HEADER_TARGET = 'pdar_entry_target'
ENTRY_HEADER_TARGET_SOURCE = 'pdar_entry_target_source'

DEFAULT_MODE = os.umask(0)
os.umask(DEFAULT_MODE)
DEFAULT_MODE = 0700 & ~DEFAULT_MODE


class _PDAREntryMeta(type):

    @property
    def type_code(cls):
        return getattr(cls, '_type_code')

    @property
    def creatable(cls):
        try:
            cls.type_code
            return True
        except AttributeError:
            return False

    _entry_classes = None

    @property
    def entry_class_map(cls):
        if _PDAREntryMeta._entry_classes is None:

            def _entry_subclasses(subclasses):
                result = []
                for class_ in subclasses:
                    if class_.creatable:
                        result.append(class_)
                    result += _entry_subclasses(class_.__subclasses__())
                return result

            _PDAREntryMeta._entry_classes = {}
            for class_ in set(_entry_subclasses([PDAREntry])):
                _PDAREntryMeta._entry_classes[class_.type_code] = class_

        return cls._entry_classes


class PDAREntry(object):

    __metaclass__ = _PDAREntryMeta

    def __init__(self, target, payload='', mode=DEFAULT_MODE,
                 orig_digest=None, dest_digest=None,
                 hash_type=DEFAULT_HASH_TYPE,
                 **kwargs):

        self._hash_type = hash_type
        if orig_digest is None or dest_digest is None:
            empty_hash = self.generate_digest('')
            if orig_digest is None:
                orig_digest = empty_hash
            if dest_digest is None:
                dest_digest = empty_hash
        
        self._mode = mode
        self._target = target
        self._orig_digest = orig_digest
        self._dest_digest = dest_digest
        self._payload = payload



    @property
    def type_code(self):
        return getattr(self, '_type_code')

    @property
    def mode(self):
        return self._mode

    @property
    def payload(self):
        return self._payload

    @property
    def target(self):
        return self._target

    @property
    def orig_digest(self):
        return self._orig_digest

    @property
    def dest_digest(self):
        return self._dest_digest

    @property
    def hash_type(self):
        return self._hash_type

    @classmethod
    def _generate_digest(cls, data, hash_type):
        return hashlib.new(hash_type, data).hexdigest()

    def generate_digest(self, data):
        return self._generate_digest(data, self.hash_type)

    def _verify_digest(self, digest, data=None, path=None):
        if data is None:
            if path is None:
                path = self.target
            with open(path, 'rb') as verify_reader:
                data = verify_reader.read()
        return digest == self.generate_digest(data)

    def verify_orig_digest(self, data=None, path=None):
        return self._verify_digest(self.orig_digest, data, path)

    def verify_dest_digest(self, data=None, path=None):
        return self._verify_digest(self.dest_digest, data, path)

    def patch(self, path=None, data=None, patcher=None):
        if path is None:
            path = self.target
        if data is None:
            if not os.path.exists(path):
                data = ''
            elif os.path.exists(path):
                with open(path, 'rb') as data_reader:
                    data = data_reader.read()
        patcher.apply_entry(self, path, data)

    def pax_dump_info(self, tfile, buf):
        info = tarfile.TarInfo(
            name=os.path.join(
                self.target, self.orig_digest))
        info.pax_headers.update({
                ENTRY_HEADER_TYPE: unicode(self.type_code),
                ENTRY_HEADER_TARGET: unicode(self.target),
                ENTRY_HEADER_ORIG_DIGEST: unicode(self.orig_digest),
                ENTRY_HEADER_DEST_DIGEST: unicode(self.dest_digest)})
        info.size = len(buf.buf)
        info.mode = self.mode
        return info

    def pax_dump(self, tfile):
        buf = StringIO(self.payload)
        buf.seek(0)
        info = self.pax_dump_info(tfile, buf)
        tfile.addfile(tarinfo=info, fileobj=buf)

    @classmethod
    def pax_load(cls, tfile, tinfo):
        headers = tinfo.pax_headers
        header_args = dict((
                key.replace('pdar_entry_', ''),
                value) for key, value in  headers.iteritems())
        header_args = dict((
                key.replace('pdar_',''), 
                value) for key, value in header_args.iteritems())
        type_cls = cls.entry_class_map[headers[ENTRY_HEADER_TYPE]]
        return type_cls(
            payload=tfile.extractfile(tinfo).read(),
            **header_args)

    @classmethod
    def read_mode(cls, source_path):
        return stat.S_IMODE(os.stat(source_path).st_mode)

    @classmethod
    def create(cls, target, orig_target, dest_target, orig_path, dest_path,
               hash_type=DEFAULT_HASH_TYPE):
        return False


class PDAREmptyEntry(PDAREntry):

    def __init__(self, target, payload='', mode=DEFAULT_MODE,
                 orig_digest='', dest_digest='', 
                 hash_type=DEFAULT_HASH_TYPE,
                 **kwargs):
        if payload != '':
            raise InvalidParameterError('invalid payload')

        super(PDAREmptyEntry, self).__init__(
            target=target, mode=mode, orig_digest=orig_digest,
            dest_digest=dest_digest, hash_type=hash_type,
            **kwargs)

    @property
    def payload(self):
        return ''


class PDARDeleteEntry(PDAREmptyEntry):

    _type_code = 'delete'

    def verify_dest_digest(self, data=None, path=None):
        if data:
            return False
        return True

    @classmethod
    def create(cls, target, orig_target, dest_target, orig_path, dest_path,
               hash_type=DEFAULT_HASH_TYPE):
        with open(os.path.join(orig_path, orig_target), 'rb') as orig_reader:
            orig_digest = cls._generate_digest(orig_reader.read(), hash_type)
        return cls(target, orig_digest=orig_digest, hash_type=hash_type)


class PDARSourceEntry(PDAREmptyEntry):

    def __init__(self, target, target_source, mode=DEFAULT_MODE,
                 orig_digest='', dest_digest='', 
                 hash_type=DEFAULT_HASH_TYPE, **kwargs):
        super(PDARSourceEntry, self).__init__(
            target=target, mode=mode, orig_digest=orig_digest,
            dest_digest=dest_digest, hash_type=hash_type, **kwargs)
        self._target_source = target_source

    @property
    def target_source(self):
        return self._target_source

    def pax_dump_info(self, tfile, buf):
        info = super(PDARSourceEntry, self).pax_dump_info(tfile, buf)
        info.pax_headers.update({
                ENTRY_HEADER_TARGET_SOURCE: self.target_source})
        return info

    def verify_orig_digest(self, data=None, path=None):
        if data:
            return False

        if path is None:
            path = self.target

        return not os.path.exists(path) and \
            self._verify_digest(self.dest_digest, path=self.target_source)

    @classmethod
    def create(cls, target, orig_target, dest_target, orig_path, dest_path,
               hash_type=DEFAULT_HASH_TYPE):
        with open(os.path.join(orig_path, orig_target), 'rb') as orig_reader:
            orig_digest = cls._generate_digest(orig_reader.read(), hash_type)

        return cls(target,
                   dest_digest=orig_digest,
                   target_source=orig_target,
                   mode=cls.read_mode(os.path.join(dest_path, dest_target)))


class PDARMoveEntry(PDARSourceEntry):

    _type_code = 'move'


class PDARCopyEntry(PDARSourceEntry):

    _type_code = 'copy'


class PDARNewEntry(PDAREntry):

    _type_code = 'new'

    def verify_orig_digest(self, data=None, path=None):
        if data:
            return False

        if path is None:
            path = self.target

        return not os.path.exists(path)

    @classmethod
    def create(cls, target, orig_target, dest_target, orig_path, dest_path,
               hash_type=DEFAULT_HASH_TYPE):
        dest_target_path = os.path.join(dest_path, dest_target)
        with open(dest_target_path, 'rb') as dest_reader:
            dest_data = dest_reader.read()
            dest_digest = cls._generate_digest(dest_data, hash_type)
        return cls(target,
                   dest_digest=dest_digest,
                   payload=dest_data,
                   mode=cls.read_mode(dest_target_path))


class PDARDiffEntry(PDAREntry):

    _type_code = 'diff'

    def __init__(self, target, payload='', mode=DEFAULT_MODE,
                 orig_digest='', dest_digest='', orig_data=None,
                 dest_data=None, hash_type=DEFAULT_HASH_TYPE,
                 **kwargs):

        if orig_data is not None or dest_data is not None:
            orig_digest = self._generate_digest(orig_data, hash_type)
            dest_digest = self._generate_digest(dest_data, hash_type)
            payload = bsdiff4.diff(orig_data, dest_data)

        super(PDARDiffEntry, self).__init__(
            target=target, payload=payload, mode=mode,
            orig_digest=orig_digest, dest_digest=dest_digest, 
            hash_type=hash_type,
            **kwargs)

    @classmethod
    def create(cls, target, orig_target, dest_target, orig_path, dest_path,
               hash_type=DEFAULT_HASH_TYPE):
        orig = os.path.join(orig_path, orig_target)
        dest = os.path.join(dest_path, dest_target)
        if not filecmp.cmp(orig, dest, False):
            with open(orig, 'rb') as orig_reader:
                with open(dest, 'rb') as dest_reader:
                    return cls(
                        target, orig_data=orig_reader.read(),
                        dest_data=dest_reader.read(),
                        mode=cls.read_mode(dest),
                        hash_type=hash_type
                        )
        return None
