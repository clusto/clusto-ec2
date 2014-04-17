#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clusto.drivers.locations.datacenters.basicdatacenter import BasicDatacenter


class VPC(BasicDatacenter):
    """
    Virtual Private Cloud driver
    """

    _driver_name = "vpc"

    def __init__(self, name_driver_entity, **kwargs):
        super(VPC, self).__init__(name_driver_entity, **kwargs)

        self.set_attr(
            key='aws', subkey='ec2_vpc_id',
            value=kwargs.get('vpc', name_driver_entity)
        )
