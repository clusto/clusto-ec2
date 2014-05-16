#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clusto.drivers.locations.datacenters.basicdatacenter import BasicDatacenter
from clustoec2.drivers.base import VPCMixin


class VPC(BasicDatacenter, VPCMixin):
    """
    Virtual Private Cloud driver
    """

    _driver_name = "vpc"

    def __init__(self, name_driver_entity, **kwargs):
        super(VPC, self).__init__(name_driver_entity, **kwargs)

        self.set_attr(
            key='aws', subkey='vpc_id',
            value=kwargs.get('vpc', name_driver_entity)
        )

    def _get_vpc(self):
        """
        Returns a boto.vpc.vpc.VPC object to work with
        """

        return self._get_object('vpc')

    def get_cidr_block(self):
        return self._get_vpc().cidr_block

    _vpc = property(lambda self: self._get_vpc())
    state = property(lambda self: self._get_state('vpc'))
    cidr_block = property(lambda self: self.get_cidr_block())
