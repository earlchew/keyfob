import os.path

from setuptools import setup, Extension

PKGNAME = 'keysafe'.lower()

setup(name=PKGNAME,
      version='1.0',
      description='Remember secrets for the duration of a login session',
      url='https://github.com/earlchew/keysafe',
      author='Earl Chew',
      author_email='earl_chew@yahoo.com',
      license='BSD-2-Clause',
      packages=[PKGNAME],
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
