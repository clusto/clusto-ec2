#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clustoec2.drivers.devices.servers import ec2server
from clustoec2.drivers.resourcemanagers import vpcconnmanager


class VPCVirtualServer(ec2server.EC2VirtualServer):

    _driver_name = 'vpcvirtualserver'
    _manager = 'vpcconnmanager'
    _mgr_driver = vpcconnmanager.VPCConnectionManager

    _instance = property(lambda self: self._get_instance())
    state = property(lambda self: self.get_state())
    private_ips = property(lambda self: self.get_private_ips())
