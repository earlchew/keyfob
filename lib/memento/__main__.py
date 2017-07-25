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

    if args.typed:
        cmd = args.command
    else:
        cmd = [
            (
                word
                if word != args.replace else
                '/dev/fd/{}'.format(rdfile.fileno())
            )
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


def createParser():

    argparser = argparse.ArgumentParser(
        description = 'Remember and recall memento')

    group = argparser.add_mutually_exclusive_group()
    group.add_argument(
        '--revoke', action = 'store_true',
        help = 'Revoke stored memento')

    group.add_argument(
        '--replace', action = 'store', default = '{}',
        help = 'Rewrite single occurence of replacement text with memento')

    group.add_argument(
        '--typed', action = 'store_true',
        help = 'Type memento rather than replacing word')

    group.add_argument(
        '--pipe', action = 'store_true',
        help = 'Write memento to stdout pipe')

    argparser.add_argument(
        '--update', action = 'store_true',
        help = 'Force memento to be updated')

    argparser.add_argument(
        '--retain', type = int, default = 60,
        help = 'Duration in minutes to retain memento'
        ' value after last use. Use zero or less to retain indefinitely.')

    argparser.add_argument(
        'name', action = 'store',
        help = 'Memento key name')

    argparser.add_argument(
        'command', nargs = '+',
        help = 'Command to run')

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
                        if args.typed:
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
        if any((args.update, args.typed, args.pipe)):
            die('Revocation conflicts with other options')
    elif args.typed:
        if not os.isatty(sys.stdin.fileno()):
            die('Typed input requires stding to be a tty')
    elif not args.pipe:
        if not args.replace:
            die('Replacement word must not be empty')
        elif sum((
                1 if word == args.replace else 0
                for word in args.command)) != 1:
            die('Exactly one {} expected'.format(args.replace))

    store = _store.Store(
        os.path.basename(os.path.dirname(__file__)),
        args.name,
        keepalive = max(0, args.retain))

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
