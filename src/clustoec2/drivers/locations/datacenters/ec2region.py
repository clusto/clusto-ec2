#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clusto.drivers.locations.datacenters.basicdatacenter import BasicDatacenter


class EC2Region(BasicDatacenter):
    """
    EC2 region driver
    """

    _driver_name = "ec2region"

    def __init__(self, name_driver_entity, **kwargs):
        super(EC2Region, self).__init__(name_driver_entity, **kwargs)

        self.set_attr(
            key='aws', subkey='ec2_region',
            value=kwargs.get('region', name_driver_entity)
        )
