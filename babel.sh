#! /bin/bash
# Copyright (C) 2012-2014 Mag. Christian Tanzer All rights reserved
# Glasauergasse 32, A--1130 Wien, Austria. tanzer@swing.co.at
# ****************************************************************************
# This script is part of the FFW program.
#
# This module is licensed under the terms of the BSD 3-Clause License
# <http://www.c-tanzer.at/license/bsd_3c.html>.
# ****************************************************************************
#
#++
# Name
#    babel
#
# Purpose
#    Extract and compile translations from Python modules and Jinja templates
#
# Revision Dates
#    27-Mar-2012 (CT) Creation
#    11-May-2012 (CT) Factor `compile` to python library's babel.sh
#    ««revision-date»»···
#--

cmd=${1:?"Specify a command: extract | language | compile"}; shift
export PYTHONPATH=$(pwd):~/CNDB:$PYTHONPATH

default_langs="en,de"
default_dirs="_FFW ."
lib=$(dirname $(python -c 'from _TFL import sos; print (sos.path.dirname (sos.__file__))'))
cndb=~/CNDB

case "$cmd" in
    "extract" )
        dirs=${1:-${default_dirs}}; shift
        ( cd ${cndb}; ./babel.sh extract )
        python ${lib}/_TFL/Babel.py extract                                          \
            -bugs_address        "tanzer@swing.co.at,ralf@runtux.com"         \
            -charset             utf-8                                        \
            -copyright_holder    "Mag. Christian Tanzer, Ralf Schlatterbeck"  \
            -global_config       ${lib}/_MOM/base_babel.cfg                   \
            -project             "FFW"                                        \
            -sort                                                             \
                $dirs
        ;;
    "language" )
        langs=${1:-${default_langs}}; shift
        dirs=${1:-${default_dirs}}; shift
        ( cd ${cndb}; ./babel.sh language "${langs}" )
        python ${lib}/_TFL/Babel.py language -languages "${langs}" -sort $dirs
        ;;
    "compile" )
        langs=${1:-${default_langs}}; shift
        ${lib}/babel.sh compile ./Command.py "${langs}" "${PYTHONPATH}"
        ;;
    * )
        echo "Unknown command $cmd; use one of"
        echo "    extract"
        echo "    language"
        echo "    compile"
        ;;
esac

### __END__ babel
