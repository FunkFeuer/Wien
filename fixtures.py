# -*- coding: utf-8 -*-
# Copyright (C) 2012-2014 Mag. Christian Tanzer All rights reserved
# Glasauergasse 32, A--1130 Wien, Austria. tanzer@swing.co.at
# #*** <License> ************************************************************#
# This module is part of the program FFW.
# 
# This module is licensed under the terms of the BSD 3-Clause License
# <http://www.c-tanzer.at/license/bsd_3c.html>.
# #*** </License> ***********************************************************#
#
#++
# Name
#    fixtures
#
# Purpose
#    Create standard objects for new scope
#
# Revision Dates
#    17-Dec-2012 (RS) Creation, move old fixtures.py to _FFW
#    27-May-2013 (CT) Remove trivial `password` values
#    28-Apr-2014 (CT) Add account `aaron@lo-res.org` and group `FFW-admin`
#    ««revision-date»»···
#--

import _CNDB._OMP.fixtures
from   _CNDB import CNDB
import _CNDB._OMP

def create (scope) :
    CNDB.OMP.fixtures.create (scope)
    Auth = scope.Auth
    Auth.Account.create_new_account_x \
        ( "christian.tanzer@gmail.com"
        , enabled = True, superuser = True, suspended = False
        )
    Auth.Account.create_new_account_x \
        ( "tanzer@swing.co.at"
        , enabled = True, suspended = False
        )
    Auth.Account.create_new_account_x \
        ( "aaron@lo-res.org"
        , enabled = True, superuser = True, suspended = False
        )
    Auth.Account.create_new_account_x \
        ( "ralf@zoo.priv.at"
        , enabled = True, superuser = True, suspended = False
        )
    Auth.Group ("FFW")
    Auth.Group ("FFW-admin")
    Auth.Account_in_Group ("tanzer@swing.co.at", "FFW")
# end def create

if __name__ == "__main__" :
    from Command import *
    db_url  = sos.environ.get ("DB_url",  "hps://")
    db_name = sos.environ.get ("DB_name", None)
    scope   = command.scope   (db_url, db_name, False)
    TFL.Environment.py_shell  ()
### __END__ fixtures
