from __future__ import absolute_import

import ctypes
import ctypes.util
import errno
import select
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


def _ioerror(err):
    return IOError(err, os.strerror(err))


class Pipeline(object):

    def __init__(self, inpfile, outfile):

        self.__inpfile = inpfile
        self.__outfile = outfile

        self.__poll = select.poll()
        self.__poll.register(
            self.__outfile.fileno(),
            select.POLLHUP | select.POLLERR)
        self.__poll.register(
            self.__inpfile.fileno(),
            select.POLLIN | select.POLLHUP | select.POLLERR)

    def close(self):

        # It seems that sys.stdin.close() and sys.stdout.close()
        # do not actually close the underlying file descriptor
        # so use os.dup2() to achieve the same effect.

        with open('/dev/null', 'r+') as nullfile:
            os.dup2(nullfile.fileno(), self.__inpfile.fileno())
            os.dup2(nullfile.fileno(), self.__outfile.fileno())

    def write(self, buf):
        self.__outfile.write(buf)

    def flush(self):
        self.__outfile.flush()

    def splice(self, size):
        while True:

            # A direct call to splice(2) can block indefinitely when
            # there is no input to read, and the output is closed. To
            # take care of this, use poll(2) to block, and splice(2) to copy.

            for fd, _ in self.__poll.poll():
                if self.__outfile.fileno() == fd:
                    raise _ioerror(errno.EPIPE)
                if self.__inpfile.fileno() == fd:
                    break
            else:
                continue

            break

        return _splice(
            self.__inpfile.fileno(), None,
            self.__outfile.fileno(), None,
            size,
            _SPLICE_F_MOVE | _SPLICE_F_NONBLOCK)
