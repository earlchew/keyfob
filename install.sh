#!/bin/sh

set -ex

[ -z "${0##/*}" ] || exec "$PWD/$0" "$@" || exit 1

# Obtain the current commit of the install script, and check if it was the one
# used to perform the last install, if any.

LABEL="$(git log -n 1 --pretty=format:%H -- "$0")" || LABEL=
[ -n "$LABEL" ] || LABEL=standalone

VERSION="$(readlink "${0%/*}/pkg/VERSION")" || VERSION=
[ -n "$VERSION" ] || VERSION=uninstalled

[ x"$VERSION" != x"$LABEL" ] || exit 0

# To prepare for the installation, clear out the target directories so that the
# installation can proceed cleanly.

rm -rf "${0%/*}/pkg"

set --
set -- "$@" git+https://github.com/earlchew/python-keyutils@memento
pip install --target "${0%/*}/pkg" "$@"

# Once the installation completes, stamp the directory atomically so that the
# next run can determine that the installer completed successfully.

ln -s "$LABEL" "${0%/*}/pkg/VERSION"
