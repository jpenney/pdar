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

import bsdiff4
import logging
import os
import stat
import shutil
import errno

from tempfile import mkstemp
from pdar.errors import *


__all__ = [
    'PDArchivePatcher', 'DEFAULT_PATCHER_TYPE']


class BaseErrorHandler(object):

    def handle_archive(self, patcher, archive, err):
        raise err

    def handle_entry(self, patcher, entry, target, data, err):
        raise err


class BasePatcher(object):

    def __init__(self, archive, path, error_handler=None):
        self._archive = archive
        self._path = path
        self._error_handler = error_handler

    @property
    def archive(self):
        return self._archive

    @property
    def path(self):
        return self._path

    @property
    def error_handler(self):
        if self._error_handler is None:
            self._error_handler = BaseErrorHandler()
        return self._error_handler

    def apply_archive_error_handler(self, archive, err):
        self.error_handler.handle_archive(self, archive, err)

    def apply_entry_error_handler(self, entry, target, data, err):
        self.error_handler.handle_entry(self, entry, target, data, err)

    def _do_apply_archive(self):
        raise NotImplementedError()

    def _do_apply_entry(self, entry, target, data):
        func = getattr(self, 'apply_entry_%s' % entry.type_code, 
                       None)
        if func is None:
            raise NotImplementedError(
                "Patcher '%s' does not support entries of type '%s'"
                % (self.__class__.__name__, entry.type_code))
        
        return func(entry, target, data)


    def apply_archive(self):
        self._do_apply_archive()

    def apply_entry(self, entry, target, data):
        try:
            self._do_apply_entry(entry, target, data)
        except Exception, err:
            self.apply_entry_error_handler(entry, target, data, err)


class PDArchiveHandler(BaseErrorHandler):

    def handle_archive(self, patcher, archive, err):
        logging.error(
            "Applying archive failed: %s", str(err))
        logging.warn(
            "Attempting to back out changes")

        for target, backup in patcher.backups.iteritems():
            target = os.path.join(patcher.path, target)
            if backup:
                shutil.copy(backup, target)
            else:
                # newly created file
                os.unlink(target)

        raise err

    def handle_entry(self, patcher, entry, target, data, err):
        #if isinstance(err, IOError) and err.errno == errno.ENOENT:
        #    logging.warn("%s: %s", err.strerror, err.filename)
        #    logging.debug(str(err))
        #    return
        logging.error(
                "Unhandled error encountered while applying delta to '%s':"
                "\n  %s",
                entry.target, str(err))
        raise err


class PDArchivePatcher(BasePatcher):

    def __init__(self, archive, path, error_handler=None):
        if error_handler is None:
            error_handler = PDArchiveHandler()

        super(PDArchivePatcher, self).__init__(
            archive, path, error_handler)

        targets = {}
        for entry in self.archive.patches:
            targets.setdefault(entry.target, [])
            targets[entry.target].append(entry)
        self._targets = dict(targets)
        self._backups = {}
        self._to_unlink = []

    @property
    def targets(self):
        return self._targets

    @property
    def backups(self):
        return self._backups

    @property
    def to_unlink(self):
        return self._to_unlink

    def _do_apply_archive(self):
        orig_path = os.getcwd()
        try:
            if self.path:
                os.chdir(self.path)
            for target, entries in self.targets.iteritems():
                for entry in entries:
                    entry.patch(patcher=self)

            for target in self.to_unlink:
                os.unlink(target)
        finally:
            os.chdir(orig_path)

        logging.debug('cleaning up unused backup files')
        for dummy, path in self.backups.iteritems():
            if path:
                try:
                    os.unlink(path)
                except IOError:
                    pass

    def _do_apply_entry(self, entry, path, data):
        if not entry.verify_orig_hash(data):
            if entry.verify_dest_hash(data):
                logging.info(
                    "patch already applied: %s", entry.target)
                return
            else:
                raise SourceFileError(
                    "original file does not contain expected data: %s"
                    % entry.target)
        logging.debug("patching %s", entry.target)

        new_data = super(PDArchivePatcher, self)._do_apply_entry(
            entry, path, data)

        if not entry.verify_dest_hash(new_data):
            raise PatchedFileError(
                "patched file does not contain expected data: %s"
                % entry.target)

        exists = os.path.exists(path)
        tmp_path = None
        if exists:
            orig_mode = stat.S_IMODE(os.stat(path).st_mode)
            fd, tmp_path = mkstemp()
            os.close(fd)

        backup_created = False
        try:
            if exists:
                shutil.copy(path, tmp_path)
            
                if not os.access(path, os.W_OK):
                    os.chmod(path, stat.S_IREAD | stat.S_IWRITE | orig_mode)

            backup_created = True
            try:
                with open(path, 'wb') as writer:
                    logging.info("writing data to %s", path)
                    writer.write(new_data)
                os.chmod(path, entry.mode)
            except Exception, err:
                if not exists:
                    logging.error("%s\nremoving new file: %s",
                                  str(err), path)
                    os.unlink(path)
                else:
                    logging.error("ERROR: %s\nrestoring unpatched file: %s",
                                  str(err), path)
                    shutil.copy(tmp_path, path)
                raise err

        finally:
            if backup_created and not entry.target in self.backups:
                self.backups[entry.target] = tmp_path
        
        
    def apply_entry_copy(self, entry, path, data):
        shutil.copy(entry.target_source, path)
        data = ''
        with open(path, 'rb') as reader:
            data = reader.read()
        return data

    def apply_entry_move(self, entry, path, data):
        new_data = self.apply_entry_copy(entry, path, data)
        self.to_unlink.append(entry.target_source)
        return new_data

    def apply_entry_delete(self, entry, path, data):
        if path is None:
            path = entry.target
        self.to_unlink.append(path)
        return ''

    def apply_entry_new(self, entry, path, data):
        return entry.payload
        
    def apply_entry_diff(self, entry, path, data):
        return bsdiff4.patch(data, entry.payload)       

DEFAULT_PATCHER_TYPE = PDArchivePatcher
