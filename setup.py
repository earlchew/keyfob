from setuptools import setup

setup(name='keyfob',
      version='1.0',
      description='Remember secrets for the duration of a login session',
      url='https://github.com/earlchew/keyfob',
      author='Earl Chew',
      author_email='earl_chew@yahoo.com',
      license='BSD-2-Clause',
      packages=['keyfob'],
      entry_points={
          'console_scripts': [
              'keyfob = keyfob.__main__:main',
          ]},
      package_dir={'' : 'lib'},
      install_requires=['keyutils'])
