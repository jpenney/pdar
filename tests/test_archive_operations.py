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
import tests
import pdar

import os
import random
import shutil
import filecmp

from pkg_resources import parse_version


class ArchiveTest(tests.ArchiveTestCase):

    def test_0001_basics(self):
        '''ensure PDArchive was created, and contains patches'''
        self.assertIsNotNone(self.pdarchive)
        self.assertGreater(len(self.pdarchive.patches),0)

    def test_0002_targets(self):
        '''validate correct targets based on dataset'''
        targets = [patch.target for patch in self.pdarchive.patches]
        changed_files = self.changed_files

        self.assertItemsNotIn(self.same_files, targets,
                              "unchanged files should not have patches in "
                              "pdar")

        self.assertItemsIn(changed_files, targets,
                           "all modified files should have patches in "
                           "pdar")

        self.assertEqual(len(changed_files), len(targets),
                              "number of modified items sholud match "
                              "number of patches in pdar")

    def test_0003_hash_values(self):
        '''validate `orig_hash` does not ever match `dest_hash`'''
        for entry in self.pdarchive.patches:
            self.assertNotEqual(entry.orig_hash, entry.dest_hash)

    def test_0003_hash_orig(self):
        '''validate `orig_hash` against files'''
        for entry in self.pdarchive.patches:
            path = os.path.join(self.orig_dir, entry.target)
            if entry.orig_hash == pdar.NEW_FILE_HASH:
                self.assertTrue(not os.path.exists(path),
                                "new files should not already exist")
            else:
                self.assertFileHashEqual(path, entry.orig_hash)

    def test_0003_hash_dest(self):
        '''validate `dest_hash` against files'''
        for entry in self.pdarchive.patches:
            path = os.path.join(self.mod_dir, entry.target)
            self.assertFileHashEqual(path, entry.dest_hash)

    def test_0004_apply_archive(self):
        '''Apply in memory pdar and validate results
        
        - clone original dataset
        - apply loaded pdar file to cloned dataset
        - filecmp.cmpfiles against destination dataset
        '''
        self._test_apply_pdarchive(self.pdarchive)


class ArchiveFileTest(tests.ArchiveFileTestCase):

    def test_0001_basics(self):
        '''ensure pdar file was written to disk'''
        self.assertTrue(os.path.exists(self.pdarchive_path))

class LoadedArchiveFileTest(tests.ArchiveFileTestCase):

    def setUp(self):
        super(LoadedArchiveFileTest, self).setUp()
        self._loaded_pdarchive = self.load_pdarchive()

    @property
    def loaded_pdarchive(self):
        return self._loaded_pdarchive

    def test_0001_basics(self):
        '''Ensure pdar file was loaded'''
        self.assertIsNotNone(self.loaded_pdarchive)
        self.assertTrue(isinstance(self.loaded_pdarchive, pdar.PDArchive))

    def test_0002_count(self):
        '''Compare number of entries'''
        self.assertEqual(len(self.pdarchive.patches), 
                         len(self.loaded_pdarchive.patches))

    def test_0003_targets(self):
        '''Compare `target` values for ecah entry'''

        self.assertItemsEqual(
            [entry.target for entry in self.loaded_pdarchive.patches],
            [entry.target for entry in self.pdarchive.patches])

    def test_0003_orig_hashes(self):
        '''Compare `orig_hash` values for each entry'''

        self.assertItemsEqual(
            [entry.orig_hash for entry in self.loaded_pdarchive.patches],
            [entry.orig_hash for entry in self.pdarchive.patches])
        
    def test_0003_dest_hashes(self):
        '''Compare `dest_hash` values for each entry'''

        self.assertItemsEqual(
            [entry.dest_hash for entry in self.loaded_pdarchive.patches],
            [entry.dest_hash for entry in self.pdarchive.patches])

    def test_0004_apply_archive(self):
        '''Apply loaded pdar file and validate results
        
        - clone original dataset
        - apply loaded pdar file to cloned dataset
        - filecmp.cmpfiles against destination dataset
        '''
        self._test_apply_pdarchive(self.loaded_pdarchive)
        
        
if __name__ == "__main__":
    tests.main()
