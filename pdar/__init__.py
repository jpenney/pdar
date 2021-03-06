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

'''Portable Delta ARchives'''

PDAR_VERSION = '1.0.1'
DEFAULT_HASH_TYPE = 'sha1'  # backwards compat

# pylint: disable=W0401
from pdar.archive import *
from pdar.entry import *
from pdar.errors import *
from pdar.patcher import *
# pylint: enable=W0401
import os
import sys


__author__ = 'Jason Penney'
__copyright__ = 'Copyright 2011, Jason Penney'
__license__ = 'Apache License, Version 2.0'
__credits__ = ['Jason Penney']
__maintainer__ = 'Jason Penney'
__version__ = '0.9.5b'
__url__ = 'http://github.com/jpenney/pdar'
__description__ = 'Portable Delta ARchives'
__long_description__ = '''
Supports creating and applying **P**ortable **D**elta **Ar**chive
(PDAR) files.  They can be used to distribute collections of patches in
the form of binary deltas wrapped in a single file.
'''

_PDAR = sys.modules[__name__]
_PDAR.__doc__ = os.linesep.join(
    [_PDAR.__description__, '', _PDAR.__long_description__])
del _PDAR
