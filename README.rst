=============================
pdar: Portable Delta Archives
=============================

``pdar`` is a Python module to support creation and application of Portable Delta Archives.  These files are similar to patch files, but they can be used on binary data files as well as text files.  

File Format
===========

Internally ``.pdar`` files are slightly modified ``.pax`` (POSIX.1-2001 tar) files, and the deltas are stored in `bsdiff <http://www.daemonology.net/bsdiff/>`_ format.

Utilities
=========

The following command line utilities are provided when the pdar Python module 
is installed.

``pdar`` 
--------

The ``pdar`` utility contains a number of commands for creation and manipulation of 
``.pdar`` files

Full Usage::

  usage: pdar [-h] [-V] [-d | -q] {info,apply,create} ...
  
  utility for manipulating portable delta archives
  
  optional arguments:
    -h, --help           show this help message and exit
    -V, --version        show version message and exit
    -d, --debug
    -q, --quiet
  
  commands:
    {info,apply,create}
      create             create pdar archive
      apply              apply pdar archive as patch
      info               show info about pdar archive


``pdar create``
^^^^^^^^^^^^^^^

The ``create`` command is used to create a new ``.pdar`` file by comparing two directory trees.  It's similar to ``diff -r``.

Example::

  $ pdar create patch.pdar /path/to/orig_files /path/to/modified files

Full Usage::

  usage: pdar create [-h] [-f] [-b]
                     archive_name path1 path2
                     [pattern [pattern ...]]
  
  create pdar archive
  
  positional arguments:
    archive_name  path to output pdar archive
    path1         path to source data
    path2         path to modified data
    pattern
  
  optional arguments:
    -h, --help    show this help message and exit
    -f, --force   overwrite existing archives
    -b, --backup  backup existing archive before overwriting
                  (implies force, existing backups may be lost).

``pdar info``
^^^^^^^^^^^^^

The ``info`` command displays information about the ``.pdar`` file and it's contents.

Example::

  $ pdar info patch.pdar

Full Usage::

  usage: pdar info [-h] archive_name
  
  show info about pdar archive
  
  positional arguments:
    archive_name  path to output pdar archive
  
  optional arguments:
    -h, --help    show this help message and exit

``pdar apply``
^^^^^^^^^^^^^^

The ``apply`` command is used to apply a ``.pdar`` file to a path, similar to the 
``patch`` utility.

Example::
  
  $ pdar apply patch.pdar /path/to/old_files

Full Usage::

  usage: pdar apply [-h] [-o OUTPUT_PATH] archive_name path
  
  apply pdar archive as patch
  
  positional arguments:
    archive_name          path to output pdar archive
    path                  path to which pdar will be applied
  
  optional arguments:
    -h, --help            show this help message and exit
    -o OUTPUT_PATH, --output-path OUTPUT_PATH
                          apply patch in alternate location,
                          rather than overwriting original files
