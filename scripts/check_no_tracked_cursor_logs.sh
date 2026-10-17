#!/bin/sh
# Pass only when git ls-files lists no .cursor/**/*.log path.
set -eu

root=$(git rev-parse --show-toplevel) || exit 1
cd "$root"

# :(glob) makes ** match zero or more directories, including a log directly under .cursor/.
tracked=$(git ls-files -- ':(glob).cursor/**/*.log') || exit 1
if [ -n "$tracked" ]; then
    printf '%s\n' "tracked .cursor/**/*.log paths:" >&2
    printf '%s\n' "$tracked"
    exit 1
fi
