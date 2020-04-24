#!/usr/bin/python
# -*- coding: utf-8 -*-
# #*** <License> ************************************************************#
# This module is part of the program FFW.
#
# This module is licensed under the terms of the BSD 3-Clause License
# <http://www.c-tanzer.at/license/bsd_3c.html>.
# #*** </License> ***********************************************************#


import sys, os
import re
import uuid
import pickle

from   datetime               import datetime, tzinfo, timedelta
from   rsclib.IP_Address      import IP4_Address, IP6_Address
from   rsclib.Phone           import Phone
from   rsclib.sqlparser       import make_naive, SQL_Parser
from   _GTW                   import GTW
from   _TFL                   import TFL
from   _TFL.pyk               import pyk
from   _CNDB                  import CNDB
import _CNDB._OMP
from   _GTW._OMP._PAP         import PAP
from   _GTW._OMP._Auth        import Auth
from   _MOM.import_MOM        import Q
from   ff_olsr.parser         import get_olsr_container
from   ff_spider.parser       import Guess
from   ff_spider.common       import unroutable, Interface, Inet4, WLAN_Config

import _TFL.CAO
import Command

def ip_mask_key (x) :
    """ Key for sorting IPs (as key of a dict iter) """
    return (x [0].mask, x [0], x [1:])
# end def ip_mask_key

class Consolidated_Interface (object) :
    """ An interface built from several redeemer devices using
        information from the OLSR MID table and the spider data.
        Originally each redeemer device will create a
        Consolidated_Device for each IP-Address it has. If a redeemer
        device has more than one IP-Address we issue a warning (this is
        not supported via the user interface of redeemer).
        These interfaces can later be merged using spider info (from the
        olsr mid table we don't know if these belong to the same or
        different interfaces of the same device).
        The original ip address is used as identity of this object, it
        is used to store the interface in a Consolidated_Device.
    """

    wl_modes = WLAN_Config.modes

    def __init__ (self, convert, device, ip, idx) :
        self.convert       = convert
        self.debug         = convert.debug
        self.device        = device
        self.idxdev        = device
        self.ip            = ip.ip
        self.idx           = idx
        self.ips           = { ip.ip : ip }
        self.merged_ifs    = []
        self.merged        = None
        self.debug         = convert.debug
        self.is_wlan       = False
        self.wlan_info     = None
        self.names         = []
        self.spider_ip     = None
        self.verbose       = convert.verbose
        assert self.device
    # end def __init__

    def create (self) :
        assert not self.merged
        dev   = self.device.net_device
        if self.debug :
            print ("device: %s ip: %s" % (self.device, self.ip))
        ffw   = self.convert.ffw
        desc  = []
        if self.names :
            desc.append ('Spider Interfaces: %s' % ', '.join (self.names))
        if self.spider_ip :
            desc.append ('Spider IP: %s' % self.spider_ip)
        desc = '\n'.join (desc) or None
        if self.is_wlan :
            iface   = self.net_interface = ffw.Wireless_Interface \
                (left = dev, name = self.ifname, desc = desc, raw = True)
            if self.wlan_info :
                std = None
                if self.wlan_info.standard is not None :
                    std  = ffw.Wireless_Standard.instance \
                        (name = self.wlan_info.standard, raw = True)
                mode = None
                if self.wlan_info.mode :
                    mode = self.wlan_info.mode.lower ()
                    mode = self.wl_modes [mode]
                bsid = self.wlan_info.bssid
                ssid = self.wlan_info.ssid
                if bsid is not None and len (bsid.split (':')) != 6 :
                    print ("INFO: Ignoring bssid: %s" % bsid)
                    bsid = None
                if ssid is not None :
                    ssid = ssid.replace (r'\x09', '\x09')
                    if len (ssid) > 32 :
                        print ("WARN: Ignoring long ssid %s" % ssid)
                        ssid = None
                iface.set_raw \
                    ( mode     = mode
                    , essid    = ssid
                    , bssid    = bsid
                    , standard = std
                    )
                if self.wlan_info.channel is not None :
                    chan = ffw.Wireless_Channel.instance \
                        (std, self.wlan_info.channel, raw = True)
                    ffw.Wireless_Interface_uses_Wireless_Channel (iface, chan)
        else :
            iface   = self.net_interface = ffw.Wired_Interface \
                (left = dev, name = self.ifname, desc = desc, raw = True)
        manager = dev.node.manager
        scope   = self.convert.scope
        for ip in pyk.itervalues (self.ips) :
            if self.verbose :
                print \
                    ( "Adding IP %s to iface: %s/%s (of dev %s)"
                    % (ip.ip, self.name, self.idxdev.name, self.device.name)
                    )
            assert not ip.done
            ip.set_done ()
            net     = IP4_Address (ip.ip, ip.cidr)
            network = ffw.IP4_Network.instance (net)
            netadr  = network.reserve (ip.ip, manager)
            ffw.Net_Interface_in_IP4_Network \
                (iface, netadr, mask_len = 32, name = self.ipname)
            if len (scope.uncommitted_changes) > 10 :
                scope.commit ()
    # end def create

    @property
    def ifname (self) :
        if self.names :
            return self.names [0]
        return self.ipname
    # end def ifname

    @property
    def ipname (self) :
        if self.idxdev.if_idx > 1 :
            return "%s-%s" % (self.name, self.idx)
        return self.name
    # end def ipname

    def merge (self, other) :
        """ Merge other interface into this one """
        assert other.device == self.device
        assert not other.merged
        if self.debug :
            print ("Merge: %s\n    -> %s" % (other, self))
            print ("Merge: dev: %s" % self.device)
        self.ips.update (other.ips)
        del other.device.interfaces [other.ip]
        self.merged_ifs.append (other)
        other.merged = self
    # end def merge

    def __getattr__ (self, name) :
        if not hasattr (self, 'idxdev') :
            raise AttributeError ("device info gone")
        r = getattr (self.idxdev, name)
        setattr (self, name, r)
        return r
    # end def __getattr__

    def __repr__ (self) :
        return "%s (ip = %s)" % (self.__class__.__name__, self.ip)
    # end def __repr__
    __str__ = __repr__

# end class Consolidated_Interface

class Consolidated_Device (object) :
    """ A device built from several redeemer devices using information
        from the OLSR MID table and the spider data.
        Initially we have a single interface with our devid.
    """
    def __init__ (self, convert, redeemer_dev) :
        self.convert       = convert
        self.debug         = convert.debug
        self.devid         = redeemer_dev.id
        self.redeemer_devs = {}
        self.interfaces    = {}
        self.merged        = None
        self.merged_devs   = []
        self.mid_ip        = None
        self.debug         = convert.debug
        self.if_idx        = 0
        self.net_device    = None
        self.hna           = False
        self.redeemer_devs [self.devid] = redeemer_dev
        self.node          = convert.node_by_id [self.id_nodes]
    # end def __init__

    @property
    def ffw_node (self) :
        return self.convert.ffw_node_by_id [self.id_nodes]
    # end def ffw_node

    def add_redeemer_ip (self, ip) :
        """ Add redeemer ip address. """
        assert not ip.id_nodes
        if ip.id_members or ip.id_members != 1 :
            print \
                ( "WARN: IP %s %s has member ID %s" \
                % (ip.ip, ip.id, ip.id_members)
                )
        assert not self.merged_devs
        assert ip.ip not in self.interfaces
        self.interfaces [ip.ip] = \
            Consolidated_Interface (self.convert, self, ip, self.if_idx)
        self.if_idx += 1
    # end def add_redeemer_ip

    def create (self) :
        """ Create device in database """
        assert self.net_device is None
        assert not self.merged
        ffw = self.convert.ffw
        if self.debug :
            print ('dev:', self.id, self.name)
        if self.if_idx > 1 :
            print \
                ( "WARN: dev %s.%s has %d ips in redeemer" \
                % (self.node.name, self.name, self.if_idx)
                )
        for d in self.merged_devs :
            if d.if_idx > 1 :
                print \
                    ( "WARN: dev %s.%s has %d ips in redeemer" \
                    % (d.node.name, d.name, self.if_idx)
                    )
        # FIXME: We want correct info from nodes directly
        # looks like most firmware can give us this info
        devtype = ffw.Net_Device_Type.instance (name = 'Generic')
        comments = dict \
            ( hardware = 'Hardware'
            , antenna  = 'Antenne'
            , comment  = 'Kommentar'
            )
        d    = self.redeemer_devs [self.devid]
        desc = '\n'.join \
            (': '.join ((v, d [k])) for k, v in pyk.iteritems (comments) if d [k])
        dev = self.net_device = ffw.Net_Device \
            ( left = devtype
            , node = self.ffw_node
            , name = self.shortest_name
            , desc = desc
            , raw  = True
            )
        self.convert.set_last_change (dev, self.changed, self.created)
        # no member info in DB:
        assert not self.id_members
        for iface in pyk.itervalues (self.interfaces) :
            iface.create ()
        self.convert.scope.commit ()
        return dev
    # end def create

    def ip_iter (self) :
        for ip in pyk.iterkeys (self.interfaces) :
            yield ip
    # end def ip_iter

    def merge (self, other) :
        """ Merge other device into this one """
        self.redeemer_devs.update (other.redeemer_devs)
        self.interfaces.update    (other.interfaces)
        if self.debug :
            print ("Merge: %s\n    -> %s" % (other, self))
        #assert not other.merged
        if other.merged :
            msg = "Merge: already merged to %s" % other.merged
            print (msg)
            raise ValueError (msg)
        for ifc in pyk.itervalues (other.interfaces) :
            ifc.device = self
        other.merged = self
        other.set_done ()
        self.merged_devs.append (other)
        assert self.devid  in self.redeemer_devs
        assert other.devid in self.redeemer_devs
    # end def merge

    @property
    def shortest_name (self) :
        """ Shortest name of all merged devices """
        sn = self.name
        for d in self.merged_devs :
            if len (d.name) < len (sn) :
                sn = d.name
        return sn
    # end def shortest_name

    def __getattr__ (self, name) :
        if not hasattr (self, 'redeemer_devs') or not hasattr (self, 'devid') :
            raise AttributeError ("redeemer dev info gone")
        r = getattr (self.redeemer_devs [self.devid], name)
        setattr (self, name, r)
        return r
    # end def __getattr__

    def __repr__ (self) :
        ndev = self.net_device
        if ndev :
            ndev = ndev.name
        return "%s (devid=%s, net_device=%s, merged=%s)" \
            % (self.__class__.__name__, self.devid, ndev, bool (self.merged))
    # end def __repr__
    __str__ = __repr__

# end class Consolidated_Device

class Convert (object) :

    def __init__ (self, cmd, scope, debug = False) :
        self.debug     = debug
        self.verbose   = cmd.verbose
        self.anonymize = cmd.anonymize
        if len (cmd.argv) > 0 :
            f  = open (cmd.argv [0])
        else :
            f = sys.stdin
        self.ip4nets = {}
        self.ip6nets = {}
        if cmd.network :
            for n in cmd.network :
                ip, comment = n.split (';', 1)
                if ':' in ip :
                    ip = IP6_Address (ip)
                    self.ip6nets [ip] = comment
                else :
                    ip = IP4_Address (ip)
                    self.ip4nets [ip] = comment
        self.spider_ignore_ip = {}
        if cmd.spider_ignore_ip :
            for i in cmd.spider_ignore_ip :
                ip_dev, ip = i.split (':')
                if ip_dev not in self.spider_ignore_ip :
                    self.spider_ignore_ip [ip_dev] = []
                self.spider_ignore_ip [ip_dev].append (ip)
        olsr = get_olsr_container (cmd.olsr_file)
        self.olsr_nodes   = {}
        for t in pyk.iterkeys (olsr.topo.forward) :
            self.olsr_nodes [t]   = True
        for t in pyk.iterkeys (olsr.topo.reverse) :
            self.olsr_nodes [t]   = True
        self.olsr_mid     = olsr.mid.by_ip
        self.olsr_hna     = olsr.hna
        self.rev_mid      = {}
        for k, v in pyk.iteritems (self.olsr_mid) :
            if k not in self.olsr_nodes :
                print ("WARN: MIB %s: not in OLSR Topology" % k)
            #assert k in self.olsr_nodes
            for mid in v :
                assert mid not in self.rev_mid
                self.rev_mid [mid] = True
        self.spider_info  = pickle.load (open (cmd.spider_dump, 'rb'))
        self.spider_devs  = {}
        self.spider_iface = {}
        for ip, dev in pyk.iteritems (self.spider_info) :
            if self.verbose :
                print ("IP:", ip)
            ignore = {}
            if str (ip) in self.spider_ignore_ip :
                ignore = dict.fromkeys (self.spider_ignore_ip [str (ip)])
            # ignore spider errors
            if not isinstance (dev, Guess) :
                continue
            dev.mainip = ip
            dev.done   = False
            for iface in pyk.itervalues (dev.interfaces) :
                iface.done = False
                for ip4 in iface.inet4 :
                    i4 = ip4.ip
                    # ignore rfc1918, link local, localnet
                    if unroutable (i4) :
                        continue
                    # ignore explicitly specified ips
                    if str (i4) in ignore :
                        print ("INFO: Ignoring %s/%s" % (ip, i4))
                        continue
                    if  (   i4 in self.spider_devs
                        and self.spider_devs [i4] != dev
                        ) :
                        print ("WARN: Device %s/%s not equal:" % (ip, i4))
                        print ("=" * 60)
                        print (dev.verbose_repr ())
                        print ("-" * 60)
                        print (self.spider_devs [i4].verbose_repr ())
                        print ("=" * 60)
                        continue
                    elif (   i4 in self.spider_iface
                         and self.spider_iface [i4] != iface
                         ) :
                        assert dev == self.spider_devs [i4]
                        spif = self.spider_iface [i4]
                        print \
                            ( "WARN: Interfaces %s/%s of dev-ip %s share ip %s"
                            % (iface.name, spif.name, ip, i4)
                            )
                        spif.names.append (iface.name)
                        if iface.is_wlan :
                            spif.is_wlan = iface.is_wlan
                            spif.wlan_info = getattr (iface, 'wlan_info', None)
                        if self.verbose :
                            print ("=" * 60)
                            print (iface)
                            print (spif)
                            print ("-" * 60)
                            print (dev.verbose_repr ())
                            print ("=" * 60)
                        iface = spif
                    self.spider_devs  [i4] = dev
                    self.spider_iface [i4] = iface
                    iface.device = dev
            if ip not in self.spider_devs :
                print ("WARN: ip %s not in dev" % ip)
                if self.verbose :
                    print ("=" * 60)
                    print (dev.verbose_repr ())
                    print ("=" * 60)
                name = 'unknown'
                assert name not in dev.interfaces
                iface = Interface (4711, name)
                iface.done = False
                dev.interfaces [name] = iface
                iface.device = dev
                iface.append_inet4 (Inet4 (ip, None, None, iface = name))
                self.spider_iface [ip] = iface
                self.spider_devs  [ip] = dev

        self.scope          = scope
        self.ffw            = self.scope.CNDB
        self.pap            = self.scope.GTW.OMP.PAP
        self.mentor         = {}
        self.rsrvd_nets     = {}
        self.ffw_node_by_id = {}
        self.node_by_id     = {}
        self.ip_by_ip       = {}
        self.email_ids      = {}
        self.manager_by_id  = {}
        self.phone_ids      = {}
        self.person_by_id   = {}
        self.member_by_id   = {}
        self.dev_by_node    = {}
        self.cons_dev       = {}

        self.parser         = SQL_Parser \
            (verbose = False, fix_double_encode = True)
        self.parser.parse (f)
        self.contents       = self.parser.contents
        self.tables         = self.parser.tables
    # end def __init__

    def set_last_change (self, obj, change_time, create_time) :
        change_time = make_naive (change_time)
        create_time = make_naive (create_time)
        self.scope.ems.convert_creation_change \
            (obj.pid, c_time = create_time, time = change_time or create_time)
        #print (obj, obj.creation_date, obj.last_changed)
    # end def set_last_change

    def create_nodes (self) :
        scope = self.scope
        for n in self.contents ['nodes'] :
            if n.id < 0 and n.id != -803 :
                print ("WARN: Ignoring Node %s/%s" % (n.name, n.id))
                continue
            if n.name == '-803' :
                n.name = 'n-803'
            print ("Processing Node: %s" % n.name)
            if len (scope.uncommitted_changes) > 100 :
                scope.commit ()
            gps = None
            #print ("LAT:", n.gps_lat_deg, n.gps_lat_min, n.gps_lat_sec)
            #print ("LON:", n.gps_lon_deg, n.gps_lon_min, n.gps_lon_sec)
            if n.gps_lat_deg is None :
                assert n.gps_lat_min is None
                assert n.gps_lat_sec is None
                assert n.gps_lon_deg is None
                assert n.gps_lon_min is None
                assert n.gps_lon_sec is None
            elif n.gps_lat_min is None :
                assert n.gps_lat_sec is None
                assert n.gps_lon_min is None
                assert n.gps_lon_sec is None
                if self.anonymize :
                    lat = "%2.2f" % n.gps_lat_deg
                    lon = "%2.2f" % n.gps_lon_deg
                else :
                    lat = "%f" % n.gps_lat_deg
                    lon = "%f" % n.gps_lon_deg
                gps = dict (lat = lat, lon = lon)
            elif n.gps_lat_min == 0 and n.gps_lat_sec == 0 :
                assert not n.gps_lon_min
                assert not n.gps_lon_sec
                if self.anonymize :
                    lat = "%2.2f" % n.gps_lat_deg
                    lon = "%2.2f" % n.gps_lon_deg
                else :
                    lat = "%f" % n.gps_lat_deg
                    lon = "%f" % n.gps_lon_deg
                gps = dict (lat = lat, lon = lon)
            else :
                assert n.gps_lat_deg == int (n.gps_lat_deg)
                assert n.gps_lat_min == int (n.gps_lat_min)
                assert n.gps_lon_deg == int (n.gps_lon_deg)
                assert n.gps_lon_min == int (n.gps_lon_min)
                lat = "%d d %d m" % (int (n.gps_lat_deg), int (n.gps_lat_min))
                lon = "%d d %d m" % (int (n.gps_lon_deg), int (n.gps_lon_min))
                if n.gps_lat_sec is not None :
                    lat = lat + " %f s" % n.gps_lat_sec
                if n.gps_lon_sec is not None :
                    lon = lon + " %f s" % n.gps_lon_sec
                gps = dict (lat = lat, lon = lon)
                if self.anonymize :
                    lat = \
                        ( n.gps_lat_deg
                        + (n.gps_lat_min or 0) / 60.
                        + (n.gps_lat_sec or 0) / 3600.
                        )
                    lon = \
                        ( n.gps_lon_deg
                        + (n.gps_lon_min or 0) / 60.
                        + (n.gps_lon_sec or 0) / 3600.
                        )
                    gps = dict (lat = "%2.2f" % lat, lon = "%2.2f" % lon)
            id = self.person_dupes.get (n.id_members, n.id_members)
            owner = self.person_by_id.get (id)
            if self.anonymize :
                manager = owner
            elif not isinstance (owner, self.pap.Person) :
                manager = self.manager_by_id [id]
            elif n.id_tech_c and n.id_tech_c != n.id_members :

                tid = self.person_dupes.get (n.id_tech_c, n.id_tech_c)
                manager = self.person_by_id.get (tid)
                assert (manager)
                if not isinstance (manager, self.pap.Person) :
                    manager = self.manager_by_id [tid]
                print ("INFO: Tech contact found: %s" % n.id_tech_c)
            else :
                manager = owner
            # node with missing manager has devices, use 0xff admin as owner
            if not owner and n.id in self.dev_by_node :
                owner = self.person_by_id.get (1)
                manager = self.manager_by_id [1]
                print \
                    ( "WARN: Node %s: member %s not found, using 1"
                    % (n.id, n.id_members)
                    )
            if owner :
                node = self.ffw.Node \
                    ( name        = n.name
                    , position    = gps
                    , show_in_map = n.map
                    , manager     = manager
                    , owner       = owner
                    , raw         = True
                    )
                self.set_last_change (node, n.changed, n.created)
                assert (node)
                self.ffw_node_by_id [n.id] = node
            else :
                print \
                    ( "ERR:  Node %s: member %s not found"
                    % (n.id, n.id_members)
                    )
    # end def create_nodes

    # first id is the one to remove, the second one is the correct one
    person_dupes = dict (( (373, 551) # checked, real dupe
                         , (338, 109) # checked, real dupe
                         , (189, 281) # checked, 189 contains almost no data
                                      # and 189 has no nodes
                         , (285, 284) # checked, real dupe
                         , (299, 297) # checked, real dupe
                         , (300, 462) # checked, real dupe
                         , (542, 586) # checked, real dupe
                         , (251, 344) # checked, real dupe
                         , (188, 614) # checked, real dupe
                         , (177, 421) # checked, real dupe
                         , (432, 433) # checked, real dupe, merge addresses
                         , ( 26, 480) # probably: almost same nick, merge adrs
                         , ( 90, 499) # FIXME: same person? merge adrs?
                                      #  90 has node 1110
                                      # 499 has node 1105 and 812
                                      # two accounts, one for HTL, one private?
                                      # maybe create company?
                                      # make company owner of 1110 and
                                      # 499 tech-c of all nodes?
                         , (505, 507) # checked, real dupe
                         , (410, 547) # checked, real dupe
                         , (712, 680) # checked, real dupe
                         , (230, 729) # checked, real dupe
                         , (375, 743) # checked, real dupe
                         , (755, 175) # checked, real dupe
                         , (219, 759) # Probably same (nick similar), merge adr
                         , (453, 454) # checked, real dupe
                         , (803, 804) # checked, real dupe
                         , (295, 556) # same gmx address, merge adr
                         , (697, 814) # checked, real dupe
                         , (476, 854) # checked, real dupe
                         , (312, 307) # checked, real dupe
                         , (351, 355) # checked, real dupe
                         , (401, 309) # checked, real dupe
                         , (871, 870) # checked, real dupe
                         , (580, 898) # checked, real dupe
                         , (894, 896) # checked, real dupe
                         , (910, 766) # checked, real dupe
                         , (926, 927) # checked, real dupe
                         , (938, 939) # checked, real dupe
                         , (584, 939) # not entirely sure but all
                                      # lowercase in both records
                                      # indicates same person
                         , (756, 758) # checked, real dupe
                         , (  0,   1) # ignore Funkfeuer Parkplatz
                         , (442,1019) # checked, old address listed in whois
                         , (1082, 1084) # checked, same email and phone
                         , (1096, 1094) # checked, same attributes
                         , (1113, 1114) # checked
                        ))
    rev_person_dupes = dict ((v, k) for k, v in pyk.iteritems (person_dupes))

    merge_adr = dict.fromkeys ((432, 26, 759, 295))

    phone_bogus   = dict.fromkeys \
        (( '01111111'
        ,  '1234567'
        ,  '0048334961656'
        ,  '001123456789'
        ,  '+972 1234567'
        ,  '003468110524227'
        ,  '1234'
        ,  '0'
        ,  '-'
        ,  '+49 1 35738755'
        ,  '974 5517 9729'
        ,  '0525001340'
        ,  '59780'
        ,  '1013'
        ,  '\\t'
        ))

    companies         = dict.fromkeys ((112, ))
    associations      = dict.fromkeys ((146, 176, 318, 438, 737, 809))
    company_actor     = {134 : 37}
    association_actor = {  1 : 15, 838 : 671}
    person_disable    = dict.fromkeys ((263, 385, 612, 621))
    person_remove     = dict.fromkeys ((549, 608))

    def try_insert_phone (self, person, m, x, c) :
        if x :
            x = x.strip ()
        if x :
            p = None
            if x in self.phone_bogus :
                return
            try :
                p = Phone (x, m.town, c)
            except ValueError as err :
                if str (err).startswith ('WARN') :
                    print (err)
                    return
            if not p :
                return
            t = self.pap.Phone.instance (* p)
            k = str (p)
            if t :
                eid = self.phone_ids [k]
                prs = self.person_by_id [eid]
                if  (  prs.pid == person.pid
                    or self.pap.Subject_has_Phone.instance (person, t)
                    ) :
                    return # don't insert twice
                print \
                    ( "WARN: %s/%s %s/%s: Duplicate phone: %s"
                    % (eid, prs.pid, m.id, person.pid, x)
                    )
            else :
                t = self.pap.Phone (* p)
                self.phone_ids [k] = m.id
            self.pap.Subject_has_Phone (person, t)
    # end def try_insert_phone

    def try_insert_email (self, person, m, attr = 'email', second = False) :
        mail  = getattr (m, attr)
        email = self.pap.Email.instance (address = mail)
        if email :
            if mail.lower () in (e.address for e in person.emails) :
                return
            eid = self.email_ids [mail.lower ()]
            prs = self.person_by_id [eid]
            print \
                ( "WARN: %s/%s %s/%s: Duplicate email: %s"
                % (eid, prs.pid, m.id, person.pid, mail)
                )
        else :
            desc = None
            if second :
                desc = "von 2. Account"
                print \
                    ( "INFO: Second email for %s/%s: %s"
                    % (m.id, person.pid, mail)
                    )
            self.email_ids [mail.lower ()] = m.id
            email = self.pap.Email (address = mail, desc = desc)
            self.pap.Subject_has_Email (person, email)
            if  (   m.id not in self.company_actor
                and m.id not in self.association_actor
                ) :
                # Some accounts are in fixtures
                auth  = self.scope.Auth.Account.instance (mail)
                if not auth :
                    auth  = self.scope.Auth.Account.create_new_account_x \
                        ( mail
                        , enabled   = True
                        , suspended = True
                        , password  = uuid.uuid4 ().hex
                        )
                self.pap.Person_has_Account (person, auth)
    # end def try_insert_email

    def try_insert_url (self, m, person) :
        hp = m.homepage
        if not hp.startswith ('http') :
            hp = 'http://' + hp
        url = self.pap.Url.instance (hp, raw = True)
        assert url is None or url.value == hp.lower ()
        if url :
            return
        url = self.pap.Url (hp, desc = 'Homepage', raw = True)
        self.pap.Subject_has_Url (person, url)
    # end def try_insert_url

    im_hash = re.compile (r"^[0-9a-f]{32}$")

    def try_insert_im (self, person, m) :
        if m.instant_messenger_nick.endswith ('@aon.at') :
            self.try_insert_email (person, m, attr = 'instant_messenger_nick')
            return
        if m.instant_messenger_nick.startswith ('alt/falsch') :
            return
        if m.instant_messenger_nick.startswith ('housing') :
            return
        if self.im_hash.match (m.instant_messenger_nick) :
            print ("WARN: Got hash in nick: %s" % m.instant_messenger_nick)
            return
        if m.instant_messenger_nick.startswith ('Wohnadresse:') :
            adr = m.instant_messenger_nick.split (':', 1) [1].strip ()
            # delimiter is a literal backslash followed by n
            street, r = adr.split (r'\n')
            plz, ort  = r.split ()
            address = self.pap.Address.instance_or_new \
                ( street     = street
                , zip        = plz
                , city       = ort
                , country    = pyk.decoded ('Austria', 'utf-8')
                )
            self.pap.Subject_has_Address (person, address)
            return
        print \
            ("INFO: Instant messenger nickname: %s" % m.instant_messenger_nick)
        im = self.pap.IM_Handle (address = m.instant_messenger_nick)
        self.pap.Subject_has_IM_Handle (person, im)
    # end def try_insert_im

    phone_types = dict \
        ( telephone   = 'Festnetz'
        , mobilephone = 'Mobil'
        , fax         = 'Fax'
        )

    def try_insert_address (self, m, person) :
        street  = ' '.join (x for x in (m.street, m.housenumber) if x)
        if street or m.town or m.zip :
            country = pyk.decoded ('Austria', 'utf-8')
            if not m.town :
                print \
                    ( 'INFO: no city (setting to "Wien"): %s/%s'
                    % (m.id, person.pid)
                    )
                m ['town'] = 'Wien'
            if not m.zip :
                if m.id == 653 :
                    m ['zip'] = 'USA'
                elif m.id == 787 :
                    m ['zip'] = '2351'
                elif m.id == 836 :
                    m ['zip'] = '1160'
                else :
                    print ("INFO: no zip: %s/%s" % (m.id, person.pid))
            elif m.zip.startswith ('I-') :
                m ['zip'] = m.zip [2:]
                country = pyk.decoded ('Italy', 'utf-8')
            if not street and not m.zip and m.town == 'Wien' :
                return
            if not street :
                print ("INFO: no street: %s/%s" % (m.id, person.pid))
                return
            address = self.pap.Address.instance_or_new \
                ( street     = street
                , zip        = m.zip
                , city       = m.town
                , country    = country
                )
            self.pap.Subject_has_Address (person, address)
    # end def try_insert_address

    def create_persons (self) :
        # FIXME: Set role for person so that person can edit only their
        # personal data, see self.person_disable
        scope = self.scope
        # ignore person dupes that have meanwhile been removed
        known_ids = {}
        for m in self.contents ['members'] :
            known_ids [m.id] = True
        for d_id, m_id in self.person_dupes.items () :
            if m_id not in known_ids or d_id not in known_ids :
                del self.person_dupes [d_id]
                del self.rev_person_dupes [m_id]
        for id, act in self.company_actor.items () :
            if id not in known_ids or act not in known_ids :
                del self.company_actor [id]
        for id, act in self.association_actor.items () :
            if id not in known_ids or act not in known_ids :
                del self.association_actor [id]

        for m in sorted (self.contents ['members'], key = lambda x : x.id) :
            if len (scope.uncommitted_changes) > 10 :
                scope.commit ()
            self.member_by_id [m.id] = m
            if m.id == 309 and m.street.startswith ("'") :
                m.street = m.street [1:]
            if m.id in self.person_remove :
                print \
                    ( "INFO: removing person %s %s %s"
                    % (m.id, m.firstname, m.lastname)
                    )
                continue
            if m.id in self.person_dupes :
                print \
                    ( "INFO: skipping person %s (duplicate of %s)"
                    % (m.id, self.person_dupes [m.id])
                    )
                continue
            if not m.firstname and not m.lastname :
                print ("WARN: skipping person, no name:", m.id)
                continue
            if not m.lastname :
                print ("WARN: skipping person, no lastname: %s" % m.id)
                continue
            if m.firstname.startswith ('Armin"/><script') :
                m.firstname = 'Armin'
            cls  = self.pap.Person
            name = ' '.join ((m.firstname, m.lastname))
            pd   = dict (name = name)
            if m.id in self.company_actor :
                cls = self.pap.Company
            elif m.id in self.association_actor :
                cls = self.pap.Association
            else :
                pd = dict (first_name = m.firstname, last_name = m.lastname)
            if self.anonymize :
                cls = self.pap.Person
                pd = dict (first_name = m.id, last_name = 'Funkfeuer')
            if self.verbose :
                typ = cls._etype.__name__.lower ()
                print ( "Creating %s: %s" % (typ, repr (name)))
            person = cls (raw = True, ** pd)
            if m.id == 1 :
                self.ff_subject = person
            if m.id not in self.rev_person_dupes :
                self.set_last_change (person, m.changed, m.created)
            self.person_by_id [m.id] = person
            if self.anonymize :
                continue
            self.try_insert_address (m, person)
            if m.email :
                self.try_insert_email (person, m)
            if m.fax and '@' in m.fax :
                self.try_insert_email (person, m, attr = 'fax')
                print \
                    ("INFO: Using email %s in fax field as email" % m.fax)
            if m.instant_messenger_nick :
                self.try_insert_im (person, m)
            for a, c in pyk.iteritems (self.phone_types) :
                x = getattr (m, a)
                self.try_insert_phone (person, m, x, c)
            if m.mentor_id and m.mentor_id != m.id :
                self.mentor [m.id] = m.mentor_id
            if m.nickname :
                nick = self.pap.Nickname (m.nickname, raw = True)
                self.pap.Subject_has_Nickname (person, nick)
            if m.homepage :
                self.try_insert_url (m, person)
            if m.id in self.companies or m.id in self.associations :
                if m.id in self.companies :
                    cls = self.pap.Company
                if m.id in self.associations :
                    cls = self.pap.Association
                name = ' '.join ((m.firstname, m.lastname))
                typ  = cls._etype.__name__.lower ()
                print ( "Creating %s: %s" % (typ, repr (name)))
                legal = cls (name = name, raw = True)
                # copy property links over
                q = self.pap.Subject_has_Property.query
                for p in q (left = person).all () :
                    self.pap.Subject_has_Property (legal, p.right)
                self.pap.Person_in_Group (person, legal)
                self.manager_by_id [m.id] = person
        if self.anonymize :
            return
        x = dict (self.company_actor)
        x.update (self.association_actor)
        for l_id, p_id in pyk.iteritems (x) :
            person = self.person_by_id [p_id]
            legal  = self.person_by_id [l_id]
            self.pap.Person_in_Group (person, legal)
            self.manager_by_id [l_id] = person
        # Retrieve info from dupe account
        for dupe, id in pyk.iteritems (self.person_dupes) :
            # older version of db or dupe removed:
            if id not in self.person_by_id :
                continue
            d = self.member_by_id [dupe]
            m = self.member_by_id [id]
            print \
                ( "Handling dupe: %s->%s %s %s" \
                % (dupe, id, d.firstname, d.lastname)
                )
            person = self.person_by_id [id]
            changed = max \
                (d for d in (m.changed, d.changed, m.created, d.created) if d)
            created = min (m.created, d.created)
            self.set_last_change (person, changed, created)
            if d.email :
                self.try_insert_email (person, d, second = True)
            for a, c in pyk.iteritems (self.phone_types) :
                x = getattr (d, a)
                self.try_insert_phone (person, d, x, c)
            if  (   d.mentor_id is not None
                and d.mentor_id != d.id
                and d.mentor_id != id
                and d.mentor_id != 305
                ) :
                print ("WARN mentor: %s->%s %s" % (d.id, id, d.mentor_id))
                assert (False)
            if d.mentor_id is not None and d.mentor_id != d.id :
                if m.id not in self.mentor :
                    self.mentor [m.id] = d.mentor_id
            if d.nickname :
                nick = self.pap.Nickname (d.nickname, raw = True)
                self.pap.Subject_has_Nickname (person, nick)
            if d.homepage :
                self.try_insert_url (d, person)
            if d.instant_messenger_nick :
                self.try_insert_im (person, d)
            if dupe in self.merge_adr :
                self.try_insert_address (d, person)
        for mentor_id, person_id in pyk.iteritems (self.mentor) :
            # can happen if a duplicate inserted this:
            if mentor_id == person_id :
                continue
            mentor_id = self.person_dupes.get (mentor_id, mentor_id)
            person_id = self.person_dupes.get (person_id, person_id)
            mentor = self.person_by_id [mentor_id]
            person = self.person_by_id [person_id]
            actors = (self.company_actor, self.association_actor)
            for a in actors :
                if mentor_id in a :
                    mentor = self.person_by_id [a [mentor_id]]
                    break
            if  (  person_id in self.company_actor
                or person_id in self.association_actor
                ) :
                self.ffw.Person_acts_for_Legal_Entity.instance_or_new \
                    (mentor, person)
            else :
                self.ffw.Person_mentors_Person (mentor, person)
    # end def create_persons

    def check_spider_dev (self, sdev, in4, ips, nodeid) :
        i4       = in4.ip
        nodename = self.ffw_node_by_id [nodeid].name
        if not routable (i4) :
            return
        ip4 = IP4_Address (i4)
        if i4 not in ips :
            print \
                ( "WARN: IP %s of spidered device %s not in mid dev for node %s"
                % (i4, sdev.mainip, nodename)
                )
            if ip4 not in self.ip_by_ip :
                print \
                    ( "WARN: IP %s of spidered device %s not in ips"
                    % (i4, sdev.mainip)
                    )
            else :
                d   = self.ip_by_ip [ip4].id_devices
                if d :
                    dev  = self.dev_by_id  [d]
                    nid  = dev.id_nodes
                    node = self.ffw_node_by_id [dev.id_nodes]
                    print \
                        ( "WARN: IP %s of spidered device %s"
                          " belongs to dev %s node %s"
                        % (i4, sdev.mainip, dev.name, node.name)
                        )
                else :
                    print \
                        ( "WARN: IP %s of spidered device %s has no device"
                        % (i4, sdev.mainip)
                        )
    # end def check_spider_dev

    def create_ips_and_devices (self) :
        # devices and reserved nets from hna table
        for ip4 in pyk.iterkeys (self.olsr_hna.by_dest) :
            for n in pyk.iterkeys (self.ip4nets) :
                if ip4 in n :
                    break
            else :
                # only subnets of one of our ip4nets
                if self.verbose :
                    print ("HNA: %s not in our networks" % ip4)
                continue
            if ip4.mask == 32 :
                if ip4 not in self.olsr_nodes :
                    if ip4 not in self.ip_by_ip :
                        print ("WARN: IP %s not in DB" % ip4)
                    else :
                        ip = self.ip_by_ip [ip4]
                        if ip.id_devices :
                            d = self.cons_dev [ip.id_devices]
                            d.hna = True
                        else :
                            # FIXME: Reserve network in database
                            self.rsrvd_nets [ip4] = True
            else :
                # FIXME: Reserve network in database
                self.rsrvd_nets [ip4] = True
                for i in ip4 :
                    if i in self.olsr_nodes :
                        print \
                            ( "WARN: IP %s from hna-range %s also in olsr nodes"
                            % (i, ip4)
                            )
                    assert i not in self.rev_mid
        if self.verbose :
            for k in pyk.iterkeys (self.rsrvd_nets) :
                print ("HNA route to: %s" % k)
        if self.debug :
            for ip4 in self.olsr_hna.by_dest :
                for nw in pyk.iterkeys (self.ip4nets) :
                    if ip4 in nw :
                        print ("HNA: %s" % ip4)

        for dev in pyk.itervalues (self.cons_dev) :
            if dev.merged :
                continue
            dev.create ()
    # end def create_ips_and_devices

    def reserve_net (self, nets, typ) :
        for net, comment in sorted (pyk.iteritems (nets), key = ip_mask_key) :
            if self.verbose :
                print (net, comment)
            r = typ.query \
                ( Q.net_address.CONTAINS (net)
                , sort_key = TFL.Sorted_By ("-net_address.mask_len")
                ).first ()
            reserver = r.reserve if r else typ
            network  = reserver (net, owner = self.ff_subject)
            if isinstance (comment, type ('')) :
                network.set_raw (desc = comment [:80])
    # end def reserve_net

    def build_device_structure (self) :
        for n in self.contents ['nodes'] :
            self.node_by_id [n.id] = n
        for d in self.contents ['devices'] :
            if d.id_nodes not in self.dev_by_node :
                self.dev_by_node [d.id_nodes] = []
            self.dev_by_node [d.id_nodes].append (d)
            self.cons_dev [d.id] = Consolidated_Device (self, d)
        for ip in self.contents ['ips'] :
            self.ip_by_ip [IP4_Address (ip.ip)] = ip
            if ip.id_devices :
                did = ip.id_devices
                self.cons_dev [did].add_redeemer_ip (ip)
            net = IP4_Address (ip.ip, ip.cidr)
            if net not in self.ip4nets :
                print ("WARN: Adding network reservation: %s" % net)
                self.ip4nets [net] = True
        # consistency check of olsr data against redeemer db
        # check nodes from topology
        for ip4 in self.olsr_nodes :
            if ip4 not in self.ip_by_ip :
                print ("WARN: ip %s from olsr topo not in ips" % ip4)
                del self.olsr_nodes [ip4]
        # check mid table
        midkey = []
        midtbl = {}
        for ip4, aliases in pyk.iteritems (self.olsr_mid) :
            if ip4 not in self.ip_by_ip :
                print ("WARN: key ip %s from olsr mid not in ips" % ip4)
                midkey.append (ip4)
            for a in aliases :
                if a not in self.ip_by_ip :
                    print ("WARN: ip %s from olsr mid not in ips" % a)
                    if ip4 not in midtbl :
                        midtbl [ip4] = []
                    midtbl [ip4].append (a)
        assert not midkey
        for k, v in pyk.iteritems (midtbl) :
            x = dict.fromkeys (self.olsr_mid [k])
            for ip4 in v :
                del x [ip4]
            self.olsr_mid [k] = x.keys ()
        # consolidate devices using information from spider data
        node_by_sdev = {}
        for mainip, sdev in sorted (pyk.iteritems (self.spider_devs)) :
            if sdev.done :
                continue
            sdev.done = True
            seen_ip = {}
            nodeid  = None
            for sif in sorted (pyk.itervalues (sdev.interfaces)) :
                assert not sif.done
                sif.done = True
                for in4 in sorted (sif.inet4) :
                    if unroutable (in4.ip) :
                        continue
                    seen_ip [in4.ip] = 1
                    i4 = IP4_Address (in4.ip)
                    ip = self.ip_by_ip.get (i4)
                    if not ip :
                        print \
                            ("WARN: ip %s from spider not in redeemer" % i4)
                        continue
                    if not ip.id_devices :
                        print ("ERR: ip %s from spider has no device" % i4)
                        continue
                    d = self.cons_dev [ip.id_devices]
                    if sdev not in node_by_sdev :
                        node_by_sdev [sdev] = {}
                    if d.id_nodes not in node_by_sdev [sdev] :
                        node_by_sdev [sdev] [d.id_nodes] = {}
                    if d.id not in node_by_sdev [sdev] [d.id_nodes] :
                        node_by_sdev [sdev] [d.id_nodes] [d.id] = {}
                    node_by_sdev [sdev] [d.id_nodes] [d.id] [in4.ip] = True
            assert mainip in seen_ip
        for sdev, nodes in sorted (pyk.iteritems (node_by_sdev)) :
            if len (nodes) > 1 :
                print \
                    ( "WARN: spider device %s expands to %s nodes: %s"
                    % ( sdev.mainip
                      , len (nodes)
                      , ', '.join
                        (self.node_by_id [n].name for n in pyk.iterkeys (nodes))
                      )
                    )
            for n, devs in sorted (pyk.iteritems (nodes)) :
                sdevs = {}
                sifs  = {}
                dev1  = None
                err   = False
                for devid, ips in sorted (pyk.iteritems (devs)) :
                    d = self.cons_dev [devid]
                    if d.merged :
                        print \
                            ("ERR: %s already merged to %s" % (d, d.merged))
                        err = True
                        continue
                    if dev1 and d.id != dev1.id :
                        if self.verbose :
                            print \
                                ( "Spider %-15s: Merging device %s.%s to %s.%s"
                                % ( sdev.mainip
                                  , d.node.name
                                  , d.name
                                  , dev1.node.name
                                  , dev1.name
                                  )
                                )
                        assert dev1 != d
                        assert not dev1.merged
                        dev1.merge (d)
                    else :
                        dev1 = d
                    for ip in sorted (pyk.iterkeys (ips)) :
                        sdevs [self.spider_devs  [ip]] = True
                        if self.spider_iface [ip] not in sifs :
                            sifs  [self.spider_iface [ip]] = {}
                        sifs  [self.spider_iface [ip]] [ip] = True

                if not err :
                    assert len (sdevs) == 1
                    if sdev not in sdevs :
                        print ("ERR:  Merged interface differ:")
                        print ("------------------------------")
                        print (sdevs.keys () [0].verbose_repr ())
                        print ("------------------------------")
                        print (sdev.verbose_repr ())
                        print ("------------------------------")
                    assert len (sifs)  >= 1
                    assert dev1
                for sif, ips in sorted (pyk.iteritems (sifs)) :
                    l = len (ips)
                    assert l >= 1
                    ifaces = {}
                    for ip in ips :
                        ifaces [ip] = dev1.interfaces [ip]
                    assert len (ifaces) == len (ips)
                    if1 = ip1 = None
                    for ip, ifc in sorted (pyk.iteritems (ifaces)) :
                        if if1 :
                            print \
                                ( "Spider %-15s: "
                                  "Merging iface %s.%s:%s to %s.%s:%s"
                                % ( sdev.mainip
                                  , d.node.name
                                  , d.name
                                  , ip
                                  , dev1.node.name
                                  , dev1.name
                                  , ip1
                                  )
                                )
                            if1.merge (ifc)
                        else :
                            if1 = ifc
                            ip1 = ip
                            if sif.is_wlan :
                                if1.is_wlan   = True
                                if1.wlan_info = getattr (sif, 'wlan_info', None)
                            if1.names = sif.names
                            if1.spider_ip = sif.device.mainip
        # compound devices from mid table
        # We index nodes by mid-table entry (by the mid key-ip address)
        # for each mid entry there can be several nodes (config bug)
        for ip4, aliases in sorted (pyk.iteritems (self.olsr_mid)) :
            nodes = {}
            ip    = self.ip_by_ip [ip4]
            if ip.id_devices :
                d = self.cons_dev [ip.id_devices]
                d.mid_ip = ip4
                nodes [d.id_nodes] = d
            else :
                print ("ERR:  key %s from mid has no device" % ip4)
            for a in sorted (aliases) :
                ip = self.ip_by_ip [a]
                if not ip.id_devices :
                    print ("ERR:  %s from mid %s has no device" % (a, ip4))
                    continue
                d  = self.cons_dev [ip.id_devices]
                d.mid_ip = ip4
                if d.id_nodes not in nodes :
                    nodes [d.id_nodes] = d
                elif d != nodes [d.id_nodes] :
                    if d.merged :
                        if d.merged != nodes [d.id_nodes] :
                            print \
                                ( "ERR: %s already merged to %s "
                                  "not merging to %s"
                                % (d, d.merged, nodes [d.id_nodes])
                                )
                        continue
                    if nodes [d.id_nodes].merged :
                        print \
                            ("ERR: %s already merged" % (nodes [d.id_nodes]))
                    else :
                        nodes [d.id_nodes].merge (d)
            if len (nodes) > 1 :
                print \
                    ("WARN: mid %s expands to %s nodes" % (ip4, len (nodes)))
    # end def build_device_structure

    def debug_output (self) :
        for k in sorted (pyk.iterkeys (self.olsr_nodes)) :
            print (k)
        for node in self.contents ['nodes'] :
            nn = pyk.encoded (node.name, 'utf-8')
            print ("Node: %s (%s)" % (nn, node.id))
            for d in self.dev_by_node.get (node.id, []) :
                print ("    Device: %s" % d.name)
    # end def debug_output

    def create (self) :
        self.build_device_structure ()
        if self.debug :
            self.debug_output       ()
        self.create_persons         ()
        self.reserve_net            (self.ip4nets, self.ffw.IP4_Network)
        self.reserve_net            (self.ip6nets, self.ffw.IP6_Network)
        self.create_nodes           ()
        self.create_ips_and_devices ()
    # end def create

# end def Convert

def _main (cmd) :
    scope = Command.scope (cmd)
    if cmd.Break :
        TFL.Environment.py_shell ()
    c = Convert (cmd, scope, debug = False)
    #c.dump ()
    c.create ()
    scope.commit ()
    scope.ems.compact ()
    scope.destroy ()
    Command.command._handle_load_auth_mig \
        (cmd, mig_auth_file = Command.command.default_mig_auth_file + ".0xff")
# end def _main

_Command = TFL.CAO.Cmd \
    ( handler         = _main
    , args            =
        ( "file:S?PG database dumpfile to convert"
        ,
        )
    , opts            =
        ( "verbose:B"
        , "create:B"
        , "anonymize:B"
        , "olsr_file:S=olsr/txtinfo.txt?OLSR dump-file to convert"
        , "spider_dump:S=Funkfeuer.dump?Spider pickle dump"
        , "network:S,?Networks already reserved"
        , "spider_ignore_ip:S,?<IP>:<IP> ignore sub-IP for spidered device"
        ) + Command.opts
    , min_args        = 1
    , defaults        = Command.command.defaults
    )

if __name__ == "__main__" :
    _Command ()
### __END__ convert_0xff
