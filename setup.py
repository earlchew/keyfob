import os
import re
import os.path
import errno
import subprocess

from setuptools import setup, Extension

def readme():
    with open('README.rst', 'r') as readmefile:
        return readmefile.read()


def gitversion():
    with open(os.devnull, 'r') as devnull:
        version = next(iter(subprocess.check_output(
            ['git', 'tag', '-l', '--points-at', 'HEAD'],
            stdin=devnull).split('\n', 1)), '').strip()

        if version:
            match = re.search(r'\d+\.\d+(\.\d+(\.\d+)?)?', version)
            version = match.group(0) if match else None

        if not version:
            version = subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], stdin=devnull).strip()[0:7]

    return version


def version(filename):

    try:
        os.stat('.git')
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise
        label = None
    else:
        label = gitversion()

    while True:
        try:
            versionfile = open(filename, 'r')
        except IOError as exc:
            if label is None or exc.errno != errno.ENOENT:
                raise
        else:
            with versionfile:
                versionlabel = versionfile.readline().rstrip()
                if label is None or label == versionlabel:
                    label = versionlabel
                    break

        assert label
        with open(filename, 'w') as versionfile:
            versionfile.write('{}\n'.format(label))
        break

    return label


PKGNAME    = 'keysafe'.lower()
PKGVERSION = version('VERSION.txt')
PKGGITREPO = 'https://github.com/earlchew/{}'.format(PKGNAME)


setup(
    name=PKGNAME,
    version=PKGVERSION,
    description='Remember secrets for the duration of a login session',
    long_description=readme(),
    url=PKGGITREPO,
    download_url='{}/archive/v{}.tar.gz'.format(PKGGITREPO, PKGVERSION),
    author='Earl Chew',
    author_email='earl_chew@yahoo.com',
    license='BSD-2-Clause',
    packages=[PKGNAME],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: BSD License',
        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Topic :: Security',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Shells',
    ],
    entry_points={
        'console_scripts': [
          '{pkgname} = {pkgname}.__main__:main'.format(pkgname=PKGNAME),
        ]},
    package_dir={'' : 'lib'},
    install_requires=['keyutils', 'cryptography'],
    include_package_data=True,
    ext_package=PKGNAME,
    ext_modules=[Extension(
        'lib{}'.format(PKGNAME),
        ['libkeysafe.c'],
        define_macros=[
            ('_GNU_SOURCE', None),
            ('MODULE_NAME', PKGNAME.upper()),
            ('MODULE_name', PKGNAME)],
        extra_compile_args=['-std=c99'])])
