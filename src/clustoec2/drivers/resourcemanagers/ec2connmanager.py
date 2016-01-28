#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

from boto import ec2
from clusto import get_entities
from clusto.drivers.base import ResourceManager
from clusto.exceptions import ResourceException


class EC2ConnManagerException(ResourceException):
    pass


class EC2ConnectionManager(ResourceManager):

    _driver_name = 'ec2connmanager'
    _attr_name = 'awsconnection'

    _conns = {}
    _properties = {
        'aws_access_key_id': None,
        'aws_secret_access_key': None,
    }

    def _connection(self, region=None):
        """
        Returns a connection "pool" (just a dict with an object per region
        used) to the calling code
        """
        r = region or 'us-east-1'
        if r not in self._conns:
            self._conns[r] = ec2.connect_to_region(
                r,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
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
        }

    def _security_group_to_dict(self, securitygroup):
        """
        Returns a dictionary with security group information
        """

        data = {
            'id': securitygroup.id,
            'region': securitygroup.region.name,
            'owner_id': securitygroup.owner_id,
        }
        if securitygroup.vpc_id:
            data['vpc_id'] = securitygroup.vpc_id
        return data

    def _connection_to_dict(self, connection):
        """
        Returns a dictionary with Instance information
        """
        return {
            'version': connection.APIVersion,
            'region': connection.region.name,
        }

    def get_all_instance_resources(self, regions=[]):
        """
        Query AWS and return all active ec2 instances and their state. If
        a list of region names is provided, only return the instances
        running in those regions
        """

        instance_resources = []

        rl = regions or [r.name for r in self._connection().get_all_regions()]

        for region in rl:

            for reservation in self._connection(region).get_all_instances():
                for instance in reservation.instances:
                    instance_resources.append({
                        'resource': self._instance_to_dict(instance),
                        'state': instance.state
                    })

        return instance_resources

    def additional_attrs(self, thing, resource, number=True):
        """
        Record the image allocation as additional resource attrs
        """

        for name, val in resource.items():
            if isinstance(val, ec2.instance.Instance):
                data = self._instance_to_dict(val)
            elif isinstance(val, ec2.securitygroup.SecurityGroup):
                data = self._security_group_to_dict(val)
            else:
                data = None

            logging.debug(data)
            if data:
                thing.add_attr(
                    key=self._attr_name,
                    subkey=name,
                    number=number,
                    value=data
                )
                return data

    def allocator(self, thing, resource=(), number=True):
        """
        Allocate a new connection-type resource to the given thing
        """

        for res in self.resources(thing):
            raise ResourceException('%s is already assigned to %s' % (
                thing.name, res.value
            ))

        region = thing.attr_value(
            key='aws', subkey='ec2_region',
            merge_container_attrs=True
        ) or 'us-east-1'

        return (self._connection_to_dict(self._connection(region)), True)

    def reconcile_additional_attrs(self):
        """
        Will correct the number of any incorrectly set attributes from
        additional attributes that share the resourcemanager's attr_key.
        """
        for ref in self.references():
            thing = get_entities([ref.entity.name])[0]
            for attr in thing.attrs(self._attr_name):
                if not attr.number == ref.number:
                    print 'Changing {0}\'s incorrect attribute...'.format(thing.name)
                    thing.set_attr(
                        key=attr.key,
                        subkey=attr.subkey,
                        # Replicate all values except the number.
                        number=ref.number,
                        value=attr.value
                    )
                    thing.del_attrs(
                        key=attr.key,
                        subkey=attr.subkey,
                        number=attr.number,
                        value=attr.value
                    )
