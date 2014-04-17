#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clusto.drivers.locations.zones import BasicZone


class VPCSubnet(BasicZone):
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
