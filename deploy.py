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
#    deploy
#
# Purpose
#    Deploy command for FFW
#
# Revision Dates
#    23-May-2012 (CT) Creation
#    31-May-2012 (CT) Remove `lib_dir` from `_defaults`
#     1-Jun-2012 (CT) Remove ancestor `GTW.OMP.deploy`
#     2-Jun-2012 (CT) Replace `config_defaults` by `Config`
#     3-Jun-2012 (CT) Factor `_Base_Command_`, add `App_Config`
#    10-Jul-2014 (CT) Derive `Command` from `CNDB.GTW.deploy.Command`, too
#    ««revision-date»»···
#--

from   __future__  import absolute_import, division, print_function #, unicode_literals

from   _CNDB                    import CNDB
from   _GTW                     import GTW
from   _TFL                     import TFL

import _CNDB.deploy

from   _Base_Command_           import _Base_Command_

class Command (_Base_Command_, CNDB.deploy.Command) :
    """Manage deployment of FFW application."""

    _defaults               = dict \
        ( project_name      = "FFW"
        )

    class App_Config (_Base_Command_.Config) :
        """Config for application: don't specify, just for internal use."""

        ### avoid auto-loading by redefining `type` to `Rel_Path`
        type                = TFL.CAO.Rel_Path

    # end class App_Config

    class Config (GTW.Werkzeug.deploy.Command.Config) :

        _default  = ".ffw.deploy.config"

    # end class Config

    class _Babel_ (GTW.Werkzeug.deploy.Command._Babel_) :

        _package_dirs       = ["."]

    # end class _Babel_

# end class Command

command = Command ()

if __name__ == "__main__" :
    command ()
### __END__ deploy
