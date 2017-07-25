from __future__ import absolute_import

import ctypes
import ctypes.util
import errno
import os

# splice(2)
#
# Refactored from https://gist.github.com/NicolasT/4519146
#
# Provide a pure Python wrapper to splice(2).

_SPLICE_F_MOVE = 1
_SPLICE_F_NONBLOCK = 2
_SPLICE_F_MORE = 4
_SPLICE_F_GIFT = 8

_libc    = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
_splice_ = _libc.splice
_splice_.c_loff_t   = ctypes.c_longlong
_splice_.c_loff_t_p = ctypes.POINTER(_splice_.c_loff_t)
_splice_.argtypes = [
    ctypes.c_int, _splice_.c_loff_t_p,
    ctypes.c_int, _splice_.c_loff_t_p,
    ctypes.c_size_t,
    ctypes.c_uint
]


def _splice(infd, inoff, outfd, outoff, size, flags):

    inoffref = (
        None if inoff is None else ctypes.byref(_splice_.c_loff_t(inoff)))

    outoffref = (
        None if outoff is None else ctypes.byref(_splice_.c_loff_t(outoff)))

    while True:
        rc = _splice_(infd, inoffref, outfd, outoffref, size, flags)
        if rc != -1:
            break
        err = ctypes.get_errno()
        if err != errno.EINTR:
            raise IOError(err, os.strerror(err))

    return rc


class Pipeline(object):

    def __init__(self, inpfile, outfile):

        self.__inpfile = inpfile
        self.__outfile = outfile

    def write(self, buf):
        self.__outfile.write(buf)

    def flush(self):
        self.__outfile.flush()

    def splice(self, size, flags=0):
        return _splice(
            self.__inpfile.fileno(), None,
            self.__outfile.fileno(), None, size, flags)
