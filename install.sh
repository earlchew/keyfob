#!/bin/sh

set -ex

[ -z "${0##/*}" ] || exec "$PWD/$0" "$@" || exit 1

# If command line options are provided, install using those options
# directly, otherwise install in-situ.
#
# When installing into a target directory, remember to also install
# the executables. For example:
#
#    install.sh
#        --target=/usr/local/pkg/keysafe
#        --install-option="--install-scripts=/usr/local/pkg/keysafe/bin"

cd "${0%/*}"

[ $# -eq 0 ] || {
    exec pip install -r requirements.txt "$@"
    exit 1
}

# Place a symlink in the source directory that points to the built
# shared library. This will allow the package to be run in-situ.

python setup.py build_ext
(
    for lib in build/lib.*/"${PWD##*/}"/*.so ; do
        [ -r lib/"${PWD##*/}/${lib##*/}" ] ||
            ln -sf ../../"$lib" lib/"${PWD##*/}"/
        exit 0
    done
    exit 1
)

# Obtain the current commit of the install script, and check if it was the one
# used to perform the last install, if any.

LABEL="$(git log -n 1 --pretty=format:%H -- "$0")" || LABEL=
[ -n "$LABEL" ] || LABEL=standalone

VERSION="$(readlink "${0%/*}/pkg/VERSION")" || VERSION=
[ -n "$VERSION" ] || VERSION=uninstalled

[ x"$VERSION" != x"$LABEL" ] || exit 0

# To prepare for the installation, clear out the target directories so that the
# installation can proceed cleanly.

rm -rf pkg

pip install --target pkg -r requirements.txt

# Once the installation completes, stamp the directory atomically so that the
# next run can determine that the installer completed successfully.

ln -s "$LABEL" "${0%/*}/pkg/VERSION"
