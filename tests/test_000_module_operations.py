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
from pkg_resources import parse_version

class TestCase(tests.TestCase):
    def _test_import_module(self, name):
        try:
            module = __import__(name)
        except ImportError, err:
            self.fail(str(err))
        self.assertIsNotNone(module)
        return module

class ImportTest(TestCase):
    
    def test_import_pdar(self):
        '''verify import of 'pdar' module'''
        pdar = self._test_import_module('pdar')
        self.assertIsNotNone(pdar.__version__)

    def test_import_pdar_errors(self):
        '''verify import of 'pdar.errors' module'''
        self._test_import_module('pdar.errors')

    def test_import_pdar_entry(self):
        '''verify import of 'pdar.entry' module'''
        self._test_import_module('pdar.entry')

    def test_import_pdar_archive(self):
        '''verify import of 'pdar.arhive' module'''
        self._test_import_module('pdar.archive')

    def test_import_pdar_patcher(self):
        '''verify import of 'pdar.patcher' module'''
        self._test_import_module('pdar.patcher')

class VersionTest(TestCase):

    def test_parse_version(self):
        '''verify 'pdar.__version__' is valid'''
        pdar = self._test_import_module('pdar')
        self.assertNotEqual(pdar.__version__, 'unknown')
        parsed_version = parse_version(pdar.__version__)
        self.assertIsNotNone(parsed_version)
        try:
            int(parsed_version[0])
        except Exception, err:
            self.fail(str(err))
        
        
if __name__ == "__main__":
    tests.main()
