#!/bin/zsh
# switch you work environment to a guestrepo shell
# set PYTHONPATH and CDPATH accordingly
#
# usage: ingrsh [name]
#
# With no argument it list all available grshell
export GUESTREPODIR="$HOME/grshells/"
ingrsh() {
    if [ $# -eq 0 ]
    then
        # the leading = disable potential alias
        =ls -1 $GUESTREPODIR | sed 's/^grshell-//'
        return 0
    fi
    grsh_path=${GUESTREPODIR}/grshell-$1
    if [ ! -d "$grsh_path" ]
    then
        echo no such guestrepo shell: '"'$grsh_path'"' >&2;
        echo 'possible values are:' >&2;
        =ls -1 $GUESTREPODIR | sed 's/^grshell-/    /' >&2;
        return 1;
    fi
    export PYTHONPATH=$grsh_path;
    export CDPATH=$grsh_path;
    cd $grsh_path;
}

_valid_grsh() {
    compadd `ingrsh`
    }

compdef _valid_grsh ingrsh
