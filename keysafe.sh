#!/bin/sh

set -e

[ -z "${0##/*}" ] || exec "$PWD/$0" --program "$0" "$@" || exit 1

[ $# -ne 0 -a x"$1" = x"--program" ] || set -- --program "$0" "$@"

! [ -h "$0" ] || exec "$(readlink -e "$0")" "$@" || exit 1

say()
{
    printf '%s\n' "$1"
}

module()
{
    set -- "${1##*/}"
    set -- "${1%.*}"
    say "$1"
}

set -- "${0%/*}/python.sh" -m "$(module "$0")" "$@"

exec "$@"
