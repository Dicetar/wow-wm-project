#!/usr/bin/env bash

MOD_WM_SPELLS_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/" && pwd )"

source "$MOD_WM_SPELLS_ROOT/conf/conf.sh.dist"

if [ -f "$MOD_WM_SPELLS_ROOT/conf/conf.sh" ]; then
    source "$MOD_WM_SPELLS_ROOT/conf/conf.sh"
fi
