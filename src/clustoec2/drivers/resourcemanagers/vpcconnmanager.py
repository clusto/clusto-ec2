#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from boto import ec2
from boto import vpc
import logging

from clusto.exceptions import ResourceException
from clustoec2.drivers.resourcemanagers import ec2connmanager


class VPCConnManagerException(ResourceException):
    pass


class VPCConnectionManager(ec2connmanager.EC2ConnectionManager):

    _driver_name = 'vpcconnmanager'
    _conns = {}

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

    def _subnet_to_dict(self, subnet):
        """
        Returns a dictionary with Instance information
        """
        return {
            'region': subnet.region.name,
            'availability_zone': subnet.availability_zone,
            'vpc_id': subnet.vpc_id,
            'subnet_id': subnet.id,
        }

    def _vpc_to_dict(self, ovpc):
        """
        Returns a dictionary with Instance information
        """
        return {
            'region': ovpc.region.name,
            'vpc_id': ovpc.id,
        }

    def additional_attrs(self, thing, resource, number=True):
        """
        Record the image allocation as additional resource attrs
        """

        for name, val in resource.items():
            if isinstance(val, vpc.subnet.Subnet):
                data = self._subnet_to_dict(val)
            elif isinstance(val, vpc.vpc.VPC):
                data = self._vpc_to_dict(val)
            elif isinstance(val, ec2.instance.Instance):
                data = self._instance_to_dict(val)
            else:
                data = None

            logging.debug(data)
            if data:
                self.set_resource_attr(
                    thing,
                    resource,
                    number=number,
                    key=name,
                    value=data
                )
                return data
