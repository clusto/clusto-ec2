#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clustoec2.drivers.resourcemanagers import ec2connmanager
from clustoec2.drivers.resourcemanagers import vpcconnmanager


class EC2Mixin(object):

    _calls = {
        'instance': 'get_all_instances',
        'vpc': 'get_all_vpcs',
        'subnet': 'get_all_subnets',
    }
    _o = None
    _mgr_driver = ec2connmanager.EC2ConnectionManager

    def _get_object(self, name, **kwargs):
        if not self._o:
            data = self.attr_value(
                key='awsconnection',
                subkey=name,
            )
            if not data:
                return None
            id = kwargs.get('id_key', '%s_id' % (name,))
            id = data.get(id)
            if not id:
                return None
            res = self._mgr_driver.resources(self)[0]
            mgr = self._mgr_driver.get_resource_manager(res)
            c = mgr._connection(res.value['region'])
            rs = getattr(c, self._calls[name])([id], **kwargs)
            self._o = rs[0]
        return self._o

    def _get_state(self, name):
        return self._get_object(name).state


class VPCMixin(EC2Mixin):
    _mgr_driver = vpcconnmanager.VPCConnectionManager
