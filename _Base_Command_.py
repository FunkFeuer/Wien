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
#    _Base_Command_
#
# Purpose
#    Base command for FFW model and deploy commands
#
# Revision Dates
#     3-Jun-2012 (CT) Creation
#    17-Dec-2013 (CT) Add `httpd_config` to `Config_Dirs._defaults`
#    ««revision-date»»···
#--

from   _TFL                   import TFL
import _TFL.Command

class _Base_Command_ (TFL.Command.Root_Command) :

    nick                  = u"FFW"

    class Config (TFL.Command.Root_Command.Config) :

        _default = ".ffw.config"

    # end class Config

# end class _Base_Command_

### __END__ _Base_Command_
