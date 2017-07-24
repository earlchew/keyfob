#!/bin/sh

[ -z "${0##/*}" ] || exec "$PWD/$0" "$@" || exit 1

! [ -h "$0" ] || exec "$(readlink -e "$0")" "$@" || exit 1

export PYTHONPATH="${0%/*}/lib:${0%/*}/pkg${PYTHONPATH+:$PYTHONPATH}"

exec python "$@"
