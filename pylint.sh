#!/bin/sh

set -e

[ -n "${0##*/*}" ] || cd "${0%/*}"

export PYTHONPATH="$PWD/lib:$PWD/pkg${PYTHONPATH+:$PYTHONPATH}"

exec pylint --rcfile=pylintrc lib/*/*.py
