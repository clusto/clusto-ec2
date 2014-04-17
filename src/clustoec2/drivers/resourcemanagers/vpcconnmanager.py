#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from boto import vpc

from clusto.exceptions import ResourceException
from clustoec2.drivers.resourcemanagers import ec2connmanager


class VPCConnManagerException(ResourceException):
    pass


class VPCConnectionManager(ec2connmanager.EC2ConnectionManager):

    _driver_name = 'vpcconnmanager'
    _attr_name = 'vpcconnmanager'
    _conns = {}
    _manager = 'vpcconnmanager'

    def _connection(self, region=None):
        """
        Returns a connection "pool" (just a dict with an object per region
        used) to the calling code
        """
        r = region or 'us-east-1'
        if r not in self._conns:
            self._conns[r] = vpc.connect_to_region(
                r,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
        return self._conns[r]

    def _instance_to_dict(self, instance):
        """
        Returns a dictionary with Instance information
        """
        return {
            'placement': instance.placement,
            'instance_id': instance.id,
            'image_id': instance.image_id,
            'region': instance.region.name,
            'subnet_id': instance.subnet_id,
            'vpc_id': instance.vpc_id,
        }
