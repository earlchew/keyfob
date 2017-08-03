import os.path

from setuptools import setup, Extension

PKGNAME = 'keysafe'.lower()


def readme():
    with open('README.rst', 'r') as readmefile:
        return readmefile.read()


setup(
    name=PKGNAME,
    version='1.0',
    description='Remember secrets for the duration of a login session',
    long_description=readme(),
    url='https://github.com/earlchew/keysafe',
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
    ext_package=PKGNAME,
    ext_modules=[Extension(
        'lib{}'.format(PKGNAME),
        ['libkeysafe.c'],
        define_macros=[
            ('_GNU_SOURCE', None),
            ('MODULE_NAME', PKGNAME.upper()),
            ('MODULE_name', PKGNAME)],
        extra_compile_args=['-std=c99'])])
