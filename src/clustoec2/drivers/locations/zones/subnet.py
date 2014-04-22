#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clusto.drivers.locations.zones import BasicZone
from clustoec2.drivers.base import VPCMixin


class VPCSubnet(BasicZone, VPCMixin):
    """
    VPC subnet driver.
    """

    _driver_name = "vpcsubnet"

    def __init__(self, name_driver_entity, **kwargs):
        super(VPCSubnet, self).__init__(name_driver_entity, **kwargs)

        self.set_attr(
            key='aws', subkey='ec2_subnet_id', value=kwargs.get(
                'subnet', name_driver_entity
            )
        )

    def _get_subnet(self):
        """
        Returns a boto.vpc.subnet.Subnet object to work with
        """

        return self._get_object('subnet')

    def get_cidr_block(self):
        return self._get_subnet().cidr_block

    _subnet = property(lambda self: self._get_subnet())
    state = property(lambda self: self._get_state('subnet'))
    cidr_block = property(lambda self: self.get_cidr_block())
