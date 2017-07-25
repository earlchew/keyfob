from __future__ import absolute_import

import os
import os.path
import sys
import getpass
import termios
import argparse
import resource
import errno
import time
import fcntl
import threading
import contextlib

from . import store as _store
from . import pipeline as _pipeline

arg0 = os.path.basename(os.path.dirname(sys.argv[0]))


def die(msg):
    sys.stderr.write('{}: {}\n'.format(arg0, msg))
    os._exit(1)


def writeMemento(outfile, memento):
    outfile.write(memento + '\n')
    outfile.flush()


def pipeMemento(inpfile, outfile, memento):
    pipeline = _pipeline.Pipeline(inpfile, outfile)
    writeMemento(pipeline, memento)
    pipelineThread = threading.Thread(
        target=lambda: runPipeline(pipeline))
    pipelineThread.daemon = True
    pipelineThread.start()


def runPipeline(pipeline):
    with contextlib.closing(pipeline):
        try:
            while pipeline.splice(8192) != 0:
                pass
        except OSError as exc:
            if exc.errno != errno.EPIPE:
                die('Unable to transfer data - {}'.format(exc))


def echoEnabled(inpfile):
    #pylint: disable=unused-variable
    (_iflag, _oflag, _cflag, lflag, _ispeed, _ospeed, _cc) = (
        termios.tcgetattr(inpfile.fileno()))

    return lflag & termios.ECHO


def typeMemento(inpfile, memento):
    for ch in memento + '\n':
        delay = 0.1
        while True:
            if echoEnabled(inpfile):
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


def spawnChild(rdfile, wrfile, args):

    cmd = [
        '/dev/fd/{}'.format(rdfile.fileno()) if word is None else word
        for word in args.command
    ]

    childpid = os.fork()
    if not childpid:

        if args.pipe:
            os.dup2(rdfile.fileno(), sys.stdin.fileno())
            rdfile.close()
        wrfile.close()

        os.execvp(args.command[0], cmd)
        os._exit(1)

    return childpid


def waitChild(childpid):
    while True:
        _, status = os.waitpid(childpid, 0)
        if os.WIFEXITED(status):
            exitcode = os.WEXITSTATUS(status)
            break
        elif os.WIFSIGNALED(status):
            exitcode = 128 + os.WTERMSIG(status)
            break
    return exitcode


def closeFds(keepfds):
    numfds, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    for fd in xrange(0, numfds):
        try:
            if fd not in keepfds:
                os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise


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
        description = 'Remember and recall private memento.',
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
        '-f', '--file', action = 'store', default = '{}',
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
        '-u', '--update', action = 'store_true',
        help = 'Force memento to be updated')

    argparser.add_argument(
        '-k', '--keep', type = int, default = 60,
        help = 'Duration in minutes to retain memento'
        ' value after last use. Use zero or less to retain indefinitely.')

    argparser.add_argument(
        'name', action = 'store',
        help = 'Memento key name.')

    argparser.add_argument(
        'command', nargs = '*',
        help = 'Command to run.')

    return argparser


def run(memento, args):

    exitcode = None

    rdfd, wrfd = os.pipe()
    try:
        with os.fdopen(wrfd, 'w') as wrfile:
            wrfd = None
            with os.fdopen(rdfd, 'r') as rdfile:
                rdfd = None

                childpid = spawnChild(rdfile, wrfile, args)
                with open('/dev/null', 'r+') as nullfile:

                    # Use stdout so that it can be used to send
                    # the memento to the child process.

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
                        # any files in common with the child process.
                        #
                        # Only stderr remains shared with the child
                        # process.

                        os.dup2(nullfile.fileno(), sys.stdout.fileno())
                        os.dup2(nullfile.fileno(), sys.stdin.fileno())

                exitcode = waitChild(childpid)
    finally:
        if rdfd is not None:
            os.close(rdfd)
        if wrfd is not None:
            os.close(wrfd)

    return 1 if exitcode is None else exitcode


def main(argv):

    args = createParser().parse_args(argv[1:])

    if args.revoke:
        if any((args.update, args.tty, args.pipe)):
            die('Revocation conflicts with other options')
    else:
        if not len(args.command):
            die('No command specified')
        if args.tty:
            if not os.isatty(sys.stdin.fileno()):
                die('Typed input requires stding to be a tty')
        elif args.pipe is not None:
            if args.pipe is not True and args.pipe != 1:
                die('Invalid pipe argument - {}'.format(args.pipe))
        else:
            if not args.file:
                die('File replacement text must not be empty')
            elif 1 != len(
                    (
                        word
                        for word in args.command
                        if word == args.file
                    )):
                die('Exactly one {} expected'.format(args.file))

            args.command = [None if word == args.file else word]

    store = _store.Store(
        os.path.basename(os.path.dirname(__file__)),
        args.name,
        keepalive = max(0, args.keep))

    rc = 1

    if args.revoke:
        store.forget()
        rc = 0
    else:

        # If an update is forced, or the memento is not available from
        # the keyring, obtain the memento from the user.

        memento = None
        if not args.update:
            memento = store.recall()
        if memento is None:
            args.update = True
            memento = readMemento()

        # If the child ran successfully, update the keyring with the
        # momento if required.

        rc = run(memento, args)
        if rc == 0 and args.update:
            store.memorise(memento)

    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv))
