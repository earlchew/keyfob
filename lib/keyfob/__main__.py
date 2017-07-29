from __future__ import absolute_import

import os
import os.path
import re
import sys
import getpass
import termios
import argparse
import resource
import errno
import time
import pipes
import fcntl
import struct
import threading
import signal
import select
import contextlib

from . import store as _store
from . import pipeline as _pipeline

_SALT    = '@'
_FILE    = '@@'
_TIMEOUT = 60
_ARG0    = os.path.basename(os.path.dirname(sys.argv[0]))


def die(msg):
    sys.stderr.write('{}: {}\n'.format(_ARG0, msg))
    os._exit(1)


def writeMemento(outfile, memento):
    try:
        outfile.write(memento + '\n')
        outfile.flush()
    except IOError as exc:
        if exc.errno != errno.EPIPE:
            die('Unable to write memento - {}'.format(exc))
        raise


def pipeMemento(inpfile, outfile, memento):
    pipeline = _pipeline.Pipeline(inpfile, outfile)
    try:
        with contextlib.closing(pipeline):
            writeMemento(pipeline, memento)
            runPipeline(pipeline)
    except IOError as exc:
        if exc.errno != errno.EPIPE:
            raise IOError(errno.EPIPE, os.strerror(errno))


def runPipeline(pipeline):
    try:
        while pipeline.splice(8192) != 0:
            pass
    except IOError as exc:
        if exc.errno != errno.EPIPE:
            die('Unable to transfer data - {}'.format(exc))
        raise


@contextlib.contextmanager
def ttySuspendInput(ttyfile):
    termios.tcflow(ttyfile.fileno(), termios.TCIOFF)
    try:
        yield
    finally:
        termios.tcflow(ttyfile.fileno(), termios.TCION)

@contextlib.contextmanager
def ttyEcho(ttyfile, enable):
    (_iflag, _oflag, _cflag, _lflag, _ispeed, _ospeed, _cc) = (
        termios.tcgetattr(ttyfile.fileno()))

    lflag = (_lflag & ~termios.ECHO) | (termios.ECHO if enable else 0)

    termios.tcsetattr(
        ttyfile.fileno(), termios.TCSADRAIN,
        [_iflag, _oflag, _cflag, lflag, _ispeed, _ospeed, _cc])
    try:
        yield
    finally:
        termios.tcsetattr(
            ttyfile.fileno(), termios.TCSADRAIN,
            [_iflag, _oflag, _cflag, _lflag, _ispeed, _ospeed, _cc])


def ttyEchoEnabled(ttyfile):
    #pylint: disable=unused-variable
    (_iflag, _oflag, _cflag, lflag, _ispeed, _ospeed, _cc) = (
        termios.tcgetattr(ttyfile.fileno()))

    return lflag & termios.ECHO


def typeMemento(inpfile, memento):
    for ch in memento + '\n':
        delay = 0.1
        while True:
            if ttyEchoEnabled(inpfile):
                time.sleep(delay)
                delay = min(delay * 2, 2) # Exponential backoff
            else:
                fcntl.ioctl(inpfile.fileno(), termios.TIOCSTI, ch)
                break


def readMemento():
    if os.isatty(sys.stdin.fileno()):
        dupfd = os.dup(sys.stdin.fileno()) # The sys.stdin file is read-only
    else:
        dupfd = os.open('/dev/tty', os.O_RDWR)
    try:
        with os.fdopen(dupfd, 'r+') as dupfile:
            dupfd = None
            return getpass.getpass('Memento: ', dupfile)
    finally:
        if dupfd is not None:
            os.close(dupfd)


def waitProcess(pid):
    while True:
        _, status = os.waitpid(pid, 0)
        if os.WIFEXITED(status):
            exitcode = os.WEXITSTATUS(status)
            break
        elif os.WIFSIGNALED(status):
            exitcode = 128 + os.WTERMSIG(status)
            break
    return exitcode


def spawnFob(rdfile, wrfile, args):

    # The fob process is an orphaned grandchild of the main application
    # process, so that it is related, but does not impede the main
    # application.

    childpid = os.fork()

    if childpid:
        exitcode = waitProcess(childpid)
        if not exitcode:
            cmd = [
                '/dev/fd/{}'.format(rdfile.fileno()) if word is None else word
                for word in args.command
            ]

            if args.pipe:
                os.dup2(rdfile.fileno(), sys.stdin.fileno())
                rdfile.close()
            wrfile.close()

            os.execvp(args.command[0], cmd)
            exitcode = 1

        os._exit(exitcode)

    grandchildpid = os.fork()
    if grandchildpid:
        os._exit(0)


def closeFds(keepfds):
    numfds, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    for fd in xrange(0, numfds):
        try:
            if fd not in keepfds:
                os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise


def readKey(filename):
    with open(filename, 'r') as keyfile:

        key = keyfile.readline().rstrip()

        # Expect process substitution to be used to supply the
        # key securely. With that in mind, search for the corresponding
        # file descriptor and close that too.

        stat    = os.fstat(keyfile.fileno())
        keystat = (stat.st_dev, stat.st_ino)

        numfds, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        for fd in xrange(0, numfds):
            if fd != keyfile.fileno():
                try:
                    stat = os.fstat(fd)
                except OSError as exc:
                    if exc.errno != errno.EBADF:
                        raise
                else:
                    if (stat.st_dev, stat.st_ino) == keystat:
                        os.close(fd)
    return key


class HelpFormatter(argparse.HelpFormatter):

    def _format_args(self, action, default_metavar):
        metavar = self._metavar_formatter(action, default_metavar)(1)[0]
        if action.nargs == argparse.ZERO_OR_MORE:
            result = '[{} ...]'.format(metavar)
        elif action.nargs == argparse.ONE_OR_MORE:
            result = '{} ...'.format(metavar)
        else:
            result = super(HelpFormatter, self)._format_args(
                action, default_metavar)
        return result

    def _metavar_formatter(self, action, default_metavar):
        if (action.metavar is None
                and action.choices is not None
                and len(action.choices) == 1):
            def formatter(tuple_size):
                return (
                    [str(choice) for choice in action.choices][0],
                ) * tuple_size
        else:
            formatter = super(HelpFormatter, self)._metavar_formatter(
                action, default_metavar)
        return formatter


def createParser():

    argparser = argparse.ArgumentParser(
        prog = os.path.basename(os.path.dirname(__file__)),
        description = 'Securely remember and recall private memento.',
        formatter_class = HelpFormatter,
        add_help = False)

    argparser.add_argument(
        '-h', '-?', '--help', action = 'help', default = argparse.SUPPRESS,
        help = 'Show this help message and exit.')

    modeGroup = argparser.add_mutually_exclusive_group()
    modeGroup.add_argument(
        '-R', '--revoke', action = 'store_true',
        help = 'Revoke the stored memento.')

    ioGroup = modeGroup.add_mutually_exclusive_group()
    ioGroup.add_argument(
        '-f', '--file', action = 'store',
        help = 'Use a file. The name of the file will be inserted'
        ' in place of the argument matching the replacement text.'
        ' The command will read the memento from the file.')

    ioGroup.add_argument(
        '-t', '--tty', action = 'store_true',
        help = 'Use /dev/tty. The command will read the memento from'
        ' the controlling terminal.')

    ioGroup.add_argument(
        '-p', '--pipe', default = None, const = True, nargs = '?',
        type = int, choices = [ 1 ],
        help = 'Use a pipe. The command will read the memento from stdin.'
        ' Normally the pipe will remain open to allow the command to'
        ' read the remaining data on stdin. Specify an argument of 1'
        ' to close stdin after sending the memento.')

    argparser.add_argument(
        '-u', '--unsalted', action = 'store_true',
        help = 'Do not require or add salt to the key')

    argparser.add_argument(
        '-T', '--timeout', type = int, action = 'store',
        help = 'Timeout in minutes to retain memento'
        ' value after last use. Use zero or less to retain indefinitely.')

    argparser.add_argument(
        '-k', '--key', action = 'store_true',
        help = 'Use the key directly from the command line'
        ' instead of reading it from a file.')

    argparser.add_argument(
        '--program',
        help=argparse.SUPPRESS)

    argparser.add_argument(
        'name', action = 'store',
        help = 'File containing key, or the key itself if --key is specified.')

    argparser.add_argument(
        'command', nargs = '*',
        help = 'Command to run.')

    return argparser


def typeCommand(ttyfile, args):

    assert os.isatty(ttyfile.fileno())

    assert not args.unsalted, args
    assert not args.key, args
    assert not args.revoke, args

    argv = [_ARG0 if args.program is None else args.program]
    if args.file is not None:
        argv.append('-f ' + pipes.quote(args.file))
    if args.tty:
        argv.append('-t')
    if args.pipe is not None:
        argv.append('-p')
        if args.pipe is not True:
            argv.append(args.pipe)
    if args.timeout is not None:
        argv.extend(['-T', args.timeout])
    argv.append('--')
    argv.append('<(echo {})'.format(pipes.quote(args.name)))
    for cmd in args.command:
        if cmd is not None:
            argv.append(pipes.quote(cmd))
        elif args.file is None:
            argv.append(_FILE)
        else:
            argv.append(pipes.quote(args.file))
    cmd =  ' '.join((str(arg) for arg in argv))

    # Flush and insert the required command into the input buffer
    # ready for use.

    with ttyEcho(ttyfile, False), ttySuspendInput(ttyfile):
        termios.tcflush(ttyfile.fileno(), termios.TCIFLUSH)
        for ch in cmd:
            fcntl.ioctl(ttyfile.fileno(), termios.TIOCSTI, ch)


def sendMemento(rdfile, wrfile, args, memento):

    with open('/dev/null', 'r+') as nullfile:

        # Use stdout so that it can be used to send
        # the memento to the application.

        os.dup2(wrfile.fileno(), sys.stdout.fileno())
        rdfile.close()
        wrfile.close()

        # Do not hold any file descriptors open beyond the
        # files opened by this process, and stdin, stdout
        # and stderr. This avoids inadvertently holding
        # flocks, etc.

        keepfds = frozenset((
            sys.stdin.fileno(),
            sys.stdout.fileno(),
            sys.stderr.fileno(),
            nullfile.fileno()))

        closeFds(keepfds)

        if args.pipe:
            pipeMemento(sys.stdin, sys.stdout, memento)
        else:
            if args.tty:
                typeMemento(sys.stdin, memento)
            else:
                writeMemento(sys.stdout, memento)

            # Release stdin and stdout to avoid holding
            # any files in common, leaving only stderr
            # shared with the aplication process.

            os.dup2(nullfile.fileno(), sys.stdout.fileno())
            os.dup2(nullfile.fileno(), sys.stdin.fileno())


def run(memento, args):

    exitcode = None

    rdfd, wrfd = os.pipe()
    try:
        with os.fdopen(wrfd, 'w') as wrfile:
            wrfd = None
            with os.fdopen(rdfd, 'r') as rdfile:
                rdfd = None

                spawnFob(rdfile, wrfile, args)
                sendMemento(rdfile, wrfile, args, memento)
    finally:
        if rdfd is not None:
            os.close(rdfd)
        if wrfd is not None:
            os.close(wrfd)

    return 1 if exitcode is None else exitcode


def main(argv=sys.argv):

    try:
        return _main(argv)
    except KeyboardInterrupt:
        return 1


def _main(argv):

    args = createParser().parse_args(argv[1:])

    if args.revoke:
        if any((args.update, args.tty, args.pipe)):
            die('Revocation conflicts with other options')
    else:
        if args.tty:
            if not os.isatty(sys.stdin.fileno()):
                die('Typed input requires stding to be a tty')
        elif args.pipe is not None:
            if args.pipe is not True and args.pipe != 1:
                die('Invalid pipe argument - {}'.format(args.pipe))
        else:
            fileword = _FILE if args.file is None else args.file
            if not fileword:
                die('File replacement text must not be empty')
            elif args.command and 1 != len(
                    [
                        word
                        for word in args.command
                        if word == fileword
                    ]):
                die('Exactly one {} expected'.format(args.file))

            args.command = [
                None if word == fileword else word
                for word in args.command
            ]

    rc = None

    if not args.revoke:
        key = args.name if args.key else readKey(args.name)

        if _SALT in key:
            if args.unsalted:
                die('Found salt {} in key'.format(_SALT))
            key, salt = key.rsplit(_SALT, 1)

        elif not args.unsalted:
            with open('/dev/tty', 'w') as ttyfile:
                if not os.isatty(ttyfile.fileno()):
                    die('Unable to find salt in key - {}'.format(args.name))

                args.name = (
                    key
                    + _SALT
                    + ('{:02x}'*3).format(
                        *struct.unpack('!' + 'B'*3, os.urandom(3))))
                typeCommand(ttyfile, args)

                rc = 127
        else:
            salt = None

    if rc is None:
        rc = 1

        timeout = (
            _TIMEOUT
            if args.timeout is None else
            max(0, args.timeout))

        store = _store.Store(
            os.path.basename(os.path.dirname(__file__)),
            key,
            salt,
            keepalive = timeout)

        if args.revoke:
            store.forget()
            rc = 0
        else:

            # If an update is forced, or the memento is not available from
            # the keyring, obtain the memento from the user.

            memento = None
            if args.command:
                memento = store.recall()
            if memento is None:
                args.update = True
                memento = readMemento()
                store.memorise(memento)

            rc = run(memento, args) if args.command else 0

    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv))
