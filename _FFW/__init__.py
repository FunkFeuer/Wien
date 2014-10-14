# -*- coding: utf-8 -*-
# Copyright (C) 2012-2013 Mag. Christian Tanzer All rights reserved
# Glasauergasse 32, A--1130 Wien, Austria. tanzer@swing.co.at
# #*** <License> ************************************************************#
# This module is part of the package FFW.
# 
# This module is licensed under the terms of the BSD 3-Clause License
# <http://www.c-tanzer.at/license/bsd_3c.html>.
# #*** </License> ***********************************************************#
#
#++
# Name
#    FFM.__init__
#
# Purpose
#    Package defining the Funkfeuer specific classes on top of the common node model
#
# Revision Dates
#     9-Jul-2014 (CT) Creation
#    ««revision-date»»···
#--

from   __future__  import absolute_import, division, print_function, unicode_literals

from   _MOM                 import MOM
import _MOM.Derived_PNS

_desc_ = """
Funkfeuer specific classes on top of the common node model.
"""

FFW = MOM.Underived_PNS ()

### __END__ FFW.__init__
