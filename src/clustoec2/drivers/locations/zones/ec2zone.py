#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from clusto.drivers.locations.zones import BasicZone


class EC2Zone(BasicZone):
    """
    EC2 zone driver.
    """

    _driver_name = "ec2zone"

    def __init__(self, name_driver_entity, **kwargs):
        super(EC2Zone, self).__init__(name_driver_entity, **kwargs)

        self.set_attr(
            key='aws', subkey='ec2_placement', value=kwargs.get(
                'placement', name_driver_entity
            )
        )
