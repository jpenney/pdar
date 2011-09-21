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

import unittest2
import hashlib
from tempfile import mkstemp, mkdtemp
import os
import random
import shutil
import pdar
import filecmp
import logging

class TestCase(unittest2.TestCase):
    
    def assertItemsIn(self, first, second, msg=None):
        for item in first:
            self.assertIn(item, second, msg)

    def assertItemsNotIn(self, first, second, msg=None):
        for item in first:
            self.assertNotIn(item, second, msg)
            
    def assertFileHashEqual(self, path, digest, hash_type, msg=None):
        if digest == '':
            digest = hashlib.new(hash_type,'').hexdigest()
        data = ''
        if os.path.exists(path):
            with open(path, 'rb') as datafile:
                data = datafile.read()
        msg = self._formatMessage(
            msg, "hash mismatch on '%s'" 
            % path)
        self.assertEqual(hashlib.new(hash_type,data).hexdigest(), 
                         digest, msg)

    def assertFileHashNotEqual(self, path, digest, hash_type, msg=None):
        if digest == '':
            digest = hashlib.new(hash_type,'').hexdigest()
        data = ''
        if os.path.exists(path):
            with open(path, 'rb') as datafile:
                data = datafile.read()
        msg = self._formatMessage(
            msg, "unexpected hash match on '%s'" 
            % path)
        self.assertNotEqual(hashlib.new(hash_type,data).hexdigest(), 
                            digest, msg)
        


DEFAULT_SIZE = 1024 * 1024 / 2

class DataSetTestCase(TestCase):

    @classmethod 
    def byte_generator(cls):
        bytes = [chr(x) for x in xrange(256)]
        while True:
            yield random.choice(bytes)
        
    @classmethod 
    def _gen_files(cls, path, fname_format, size=DEFAULT_SIZE, num_files=5,
                   mode='wb'):
        files = []
        max_size_diff = size / 4
        min_size_diff = -1 * max_size_diff
        data_source = cls.byte_generator()

        for fname in (
            os.path.join(
                path, fname_format % num) for num in xrange(num_files)):
            with open(fname, mode) as datafile:
                if datafile.tell() == 0:
                    # Write some nulls out at the beginning of the file
                    # so that 'file' and 'diff' commands recognize the file 
                    # as binary.  This is not a requirement, but it prevents
                    # me from messing up my terminal accidentally when 
                    # debugging things -- jpenney
                    datafile.write(chr(0) * 4) 
                to_write = size + random.randint(
                    min_size_diff, max_size_diff)
                eof = datafile.tell() + to_write

                while datafile.tell() < eof:
                    repeat = to_write/100
                    if repeat < 1:
                        repeat = 1
                    datafile.write(next(data_source) * repeat)
            files.append(os.path.relpath(fname, path))
        return files

    @classmethod
    def files_to_paths(cls, files, path):
        return (os.path.join(path, fname) for fname in files)

    @classmethod
    def _make_data_set(cls):
        cls._workdir = mkdtemp(prefix=__name__ + '.')
        cls._orig_dir = os.path.join(cls._workdir, 'orig_dir')
        cls._mod_dir = os.path.join(cls._workdir, 'mod_dir')
        os.mkdir(cls._orig_dir)
       
        cls._same_files = cls._gen_files(cls._orig_dir, "%04d.same")
        cls._diff_files = cls._gen_files(cls._orig_dir, "%04d.diff")
        cls._append_files = cls._gen_files(cls._orig_dir, "%04d.append")
        cls._mod_files = cls._gen_files(cls._orig_dir, "%04d.mod")
        cls._moved_files = cls._gen_files(cls._orig_dir, "%04d.moved")

        shutil.copytree(cls._orig_dir, cls._mod_dir)
        dircmp = filecmp.dircmp(cls._orig_dir, cls._mod_dir)
        if not set(dircmp.left_list) == set(dircmp.right_list) == \
                set(dircmp.common):
            raise RuntimeError("error setting up data set")
        
        cls._deleted_files = cls._gen_files(cls._orig_dir, "%04d.delete")
        cls._new_files = cls._gen_files(cls._mod_dir, "%04d.new")

        # rename "moved" files
        for fname in cls.files_to_paths(cls._moved_files, cls._orig_dir):
            fname_fix = fname.replace('moved', 'move')
            logging.debug("moving '%s' -> '%s'", fname, fname_fix)
            shutil.move(fname, fname_fix)
        # copy same files and moved files
        cls._copied_files = []
        for fname in list(
            cls.files_to_paths(cls._same_files, cls._mod_dir)) + \
            list(cls.files_to_paths(cls._moved_files, cls._mod_dir)):
            dest_fname = fname + '.copied'
            shutil.copy(fname, dest_fname)
            cls._copied_files.append(os.path.relpath(dest_fname, cls._mod_dir))

        # replace diff files
        #for fname in cls.files_to_paths(cls._diff_files, cls._mod_dir):
        #    os.unlink(fname)
        cls._gen_files(cls._mod_dir, "%04d.diff")

        # append to files
        cls._gen_files(cls._mod_dir, "%04d.append", mode="a+b", 
                       size=(DEFAULT_SIZE/4)+1)

        # modify files
        data_source = cls.byte_generator()
        for fname in cls.files_to_paths(cls._mod_files, cls._mod_dir):
            with open(fname, "a+b") as datafile:
                datafile.seek(0)
                datafile.read()
                eof = datafile.tell()
                datafile.seek(0)
                data_size = (eof/10) + 1

                for seekpoint in (
                    random.randint(0,eof) for dummy in xrange(5)):
                    datafile.seek(seekpoint)
                    write_len = random.randint(0, data_size)
                    eow = seekpoint + write_len
                    while datafile.tell() < eow:
                        repeat = (eow - seekpoint)/100
                        if repeat < 1:
                            repeat = 1
                        datafile.write(next(data_source) * repeat)

        
    @classmethod
    def setUpClass(cls):
        super(DataSetTestCase, cls).setUpClass()
        cls._make_data_set()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._workdir):
            shutil.rmtree(cls._workdir, True)

    @property
    def workdir(self):
        return self._workdir

    @property
    def orig_dir(self):
        return self._orig_dir

    @property
    def mod_dir(self):
        return self._mod_dir

    @property
    def same_files(self):
        return self._same_files

    @property
    def diff_files(self):
        return self._diff_files

    @property 
    def append_files(self):
        return self._append_files

    @property
    def mod_files(self):
        return self._mod_files

    @property 
    def moved_files(self):
        return self._moved_files

    @property
    def copied_files(self):
        return self._copied_files

    @property
    def new_files(self):
        return self._new_files

    @property
    def deleted_files(self):
        return self._deleted_files

    @property
    def changed_files(self):
        return self.changed_dest_files + self.deleted_files

    @property
    def changed_dest_files(self):
        return self.diff_files + self.append_files + self.mod_files + \
            self.new_files + self.moved_files + self.copied_files

class ArchiveTestCase(DataSetTestCase):

    def setUp(self):
        super(ArchiveTestCase, self).setUp()
        self._pdarchive = pdar.PDArchive(self.orig_dir, self.mod_dir)


    def _test_apply_pdarchive(self, pdarchive):
        patch_dir = os.path.join(self.workdir, 'patch_dir')
        shutil.copytree(self.orig_dir, patch_dir)
        self.addCleanup(shutil.rmtree, patch_dir)
        pdarchive.patch(patch_dir)

        dircmp = filecmp.dircmp(self._mod_dir, patch_dir)
        self.assertItemsEqual(dircmp.left_list, dircmp.right_list,
                              'filecmp.dircmp left_list should match '
                              'right_list')

    @property
    def pdarchive(self):
        return self._pdarchive

class ArchiveFileTestCase(ArchiveTestCase):

    def setUp(self):
        super(ArchiveFileTestCase, self).setUp()
        dummy, path = mkstemp(suffix='.pdar', dir=self.workdir)
        os.unlink(path)
        self._pdarchive_path = path
        self.pdarchive.save(self._pdarchive_path)
        self.addCleanup(os.unlink, self._pdarchive_path)

    @property
    def pdarchive_path(self):
        return self._pdarchive_path

    def load_pdarchive(self):
        return pdar.PDArchive.load(self.pdarchive_path)

def main():
    unittest2.main()

