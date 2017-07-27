#!/bin/sh

set -e

[ -z "${0##/*}" ] || exec "$PWD/$0" "$@" || exit 1

! [ -h "$0" ] || exec "$(readlink -e "$0")" "$@" || exit 1

set -- "${0%/*}/python.sh" -m keyfob "$@"

exec "$@"
