#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

import os
import sys

import clusto
from clusto import script_helper
from clusto import drivers
from clustoec2 import drivers as ec2_drivers


class BootstrapEc2(script_helper.Script):
    """
    Will bootstrap your ec2 infrastructure (regions, zones, etc)
    """

    def __init__(self):
        script_helper.Script.__init__(self)

    def _add_arguments(self, parser):
        parser.add_argument(
            '-k', '--aws-key', required=not os.environ.get('AWS_ACCESS_KEY_ID', False),
            help='Your AWS key id, defaults to ENV[AWS_ACCESS_KEY_ID] if set',
            default=os.environ.get('AWS_ACCESS_KEY_ID')
        )
        parser.add_argument(
            '-s', '--aws-secret-key', required=not os.environ.get('AWS_SECRET_ACCESS_KEY', False),
            help='Your AWS key secret, defaults to ENV[AWS_SECRET_ACCESS_KEY] if set',
            default=os.environ.get('AWS_SECRET_ACCESS_KEY')
        )
        parser.add_argument(
            '--vpc-manager', '-V', default='vpcconnman',
            help='Name of the VPC Connection Manager you want to use'
        )
        parser.add_argument(
            '--conn-manager', '-c', default='ec2connman',
            help='Name of the EC2 Connection Manager you want to use'
        )
        parser.add_argument(
            '--add-to-pool', '-p', default=None,
            help='If given, amazon "location" objects will be inserted in '
            'the given pool'
        )
        parser.add_argument(
            '--no-import', default=False, action='store_true',
            help='Skip importing existing resources'
        )

    def add_subparser(self, subparsers):
        parser = self._setup_subparser(subparsers)
        self._add_arguments(parser)

    def run(self, args):
        self.debug('Grab or create the VM Manager')
        try:
            ec2connman = clusto.get_by_name(
                args.conn_manager,
                assert_driver=ec2_drivers.resourcemanagers.EC2ConnectionManager
            )
            vpcman = clusto.get_by_name(
                args.vpc_manager,
                assert_driver=ec2_drivers.resourcemanagers.VPCConnectionManager
            )
        except LookupError:
            if not args.aws_key and not args.aws_secrets_key:
                raise Exception(
                    'you must specify both an aws_access_key_id '
                    'and an aws_secret_access_key if you don\'t already have '
                    'an EC2ConnectionManager'
                )
            ec2connman = clusto.get_or_create(
                args.conn_manager,
                ec2_drivers.resourcemanagers.EC2ConnectionManager,
                aws_access_key_id=args.aws_key,
                aws_secret_access_key=args.aws_secret_key
            )
            self.info(
                'Created the "%s" EC2 Connection Manager' % (
                    args.conn_manager
                )
            )
            vpcman = ec2_drivers.resourcemanagers.VPCConnectionManager(
                args.vpc_manager,
                aws_access_key_id=args.aws_key,
                aws_secret_access_key=args.aws_secret_key
            )
            self.info(
                'Created the "%s" VPC Connection Manager' % (
                    args.vpc_manager
                )
            )

        container_pool = None
        if args.add_to_pool:
            container_pool = clusto.get_or_create(
                args.add_to_pool, drivers.pool.Pool)
        self.info('Creating all available regions')
        for region in ec2connman._connection().get_all_regions():
            curconn = ec2connman._connection(region.name)
            vpcconn = vpcman._connection(region.name)
            region_entity = clusto.get_or_create(
                region.name,
                ec2_drivers.locations.datacenters.EC2Region,
                region=region.name
            )
            region_entity.set_attr(
                key='aws', subkey='ec2_region',
                value=region.name
            )
            self.debug('Created "%s" region' % (region.name, ))
#           Create all VPCs (if any)
            self.info(
                'Creating all VPCs (if any) for region %s' % (
                    region.name,
                )
            )
            for v in vpcconn.get_all_vpcs():
                v_entity = clusto.get_or_create(
                    v.id,
                    ec2_drivers.locations.datacenters.VPC,
                    vpc=v.id,
                )
                if v_entity not in vpcman.referencers():
                    vpcman.allocate(v_entity)
                    vpcman.additional_attrs(
                        v_entity,
                        resource={'vpc': v}
                    )
                self.debug('Created "%s" VPC' % (v.id, ))
                if v_entity not in region_entity:
                    region_entity.insert(v_entity)
#               Create all subnets (if any)
                self.info(
                    'Creating all subnets (if any) for VPC %s' % (
                        v.id,
                    )
                )
                for sn in vpcconn.get_all_subnets(filters={'vpc_id': v.id}):
                    sn_entity = clusto.get_or_create(
                        sn.id,
                        ec2_drivers.locations.zones.VPCSubnet,
                        subnet=sn.id,
                    )
                    if sn_entity not in vpcman.referencers():
                        vpcman.allocate(sn_entity)
                        vpcman.additional_attrs(
                            sn_entity,
                            resource={'subnet': sn}
                        )
                    if sn_entity not in v_entity:
                        v_entity.insert(sn_entity)
                        self.debug('Inserted subnet %s in VPC %s' % (
                            sn.id, v.id, )
                        )
#           Create all zones
            self.info(
                'Creating all availability zones for region %s' % (
                    region.name,
                )
            )
            for zone in curconn.get_all_zones():
                zone_entity = clusto.get_or_create(
                    zone.name,
                    ec2_drivers.locations.zones.EC2Zone,
                    placement=zone.name
                )
                zone_entity.set_attr(
                    key='aws', subkey='ec2_placement',
                    value=zone.name
                )
                self.debug('Created "%s" zone' % (zone.name, ))
                if zone_entity not in region_entity:
                    region_entity.insert(zone_entity)
                self.debug(
                    'Inserted "%s" zone in "%s" region' % (
                        zone.name, region.name,
                    )
                )
#               if there are subnets in this region, insert them
                for sn in vpcconn.get_all_subnets(
                    filters={
                        'availability-zone': zone.name,
                    }
                ):
                    sn_entity = clusto.get_by_name(sn.id)
                    if sn_entity not in zone_entity:
                        zone_entity.insert(sn_entity)
                        self.debug('Inserted %s subnet in %s AZ' % (
                            sn.id, zone.name, )
                        )
            if container_pool and region_entity not in container_pool:
                self.debug(
                    'Adding region %s to pool %s' % (
                        region.name, args.add_to_pool,
                    )
                )
                container_pool.insert(region_entity)

        self.info('Creating all security groups')
        sgs = vpcman._connection().get_all_security_groups()
        belong = {}
        for sg in sgs:
            belong[sg.id] = [_.id for _ in sg.instances()]
        sgs = [(_.id, _.name, _.region.name, _.vpc_id) for _ in sgs]
        for sg_id, sg_name, region_name, vpc_id in sgs:
            self.debug(
                'Importing %s (%s), region: %s, vpc? %s' % (
                    sg_name, sg_id, region_name, bool(vpc_id),
                )
            )
            sg_ent = clusto.get_or_create(
                sg_id,
                ec2_drivers.categories.securitygroup.EC2SecurityGroup,
                group_id=sg_id,
                group_name=sg_name
            )
            if vpc_id:
                parent = clusto.get_by_name(vpc_id)
            else:
                parent = clusto.get_by_name(region_name)
            if sg_ent not in parent:
                self.debug('Inserting security group %s into %s' % (sg_id, vpc_id or region_name,))
                parent.insert(sg_ent)

        if not args.no_import:
            self.info('Creating all instances')
            for reservations in vpcman._connection().get_all_instances():
                for instance in reservations.instances:
                    idriver = ec2_drivers.devices.servers.EC2VirtualServer
                    connman = ec2connman
                    name = instance.tags.get('Name', instance.id).lower().replace(' ', '_')
                    if instance.vpc_id and instance.subnet_id:
                        idriver = ec2_drivers.devices.servers.VPCVirtualServer
                        connman = vpcman
                    self.debug('Creating %s instance (%s)' % (name, idriver, ))
                    instance_entity = clusto.get_or_create(
                        name,
                        idriver,
                    )
                    placement = clusto.get_by_name(instance.subnet_id or instance.placement)
                    self.debug('Inserting instance %s into %s' % (name, placement, ))
                    if instance_entity not in placement:
                        placement.insert(instance_entity)
                    instance_entity.set_attr(
                        key='aws', subkey='ec2_instance_type',
                        value=instance.instance_type
                    )
                    if instance.key_name is not None:
                        instance_entity.set_attr(
                            key='aws', subkey='ec2_key_name',
                            value=instance.key_name
                        )
                    instance_entity.set_attr(
                        key='aws',
                        subkey='ec2_instance_id',
                        value=instance.id,
                    )

                    for sg, instances in belong.items():
                        if instance.id in instances:
                            sg_ent = clusto.get_by_name(sg)
                            if instance_entity not in sg_ent:
                                self.debug(
                                    'Adding instance %s to security group %s' % (
                                        instance.id, sg,
                                    )
                                )
                                sg_ent.insert(instance_entity)

                    self.debug('Allocating instance %s from %s' % (name, connman, ))
                    if instance_entity not in connman.referencers():
                        connman.allocate(instance_entity)
                        connman.additional_attrs(
                            instance_entity,
                            resource={'instance': instance}
                        )
                        instance_entity.update_metadata()
                    self.debug('%s is imported' % (instance,))
        self.info('Finished, AWS objects should now be in the database')


def main():
    bootstrap, args = script_helper.init_arguments(BootstrapEc2)
    return(bootstrap.run(args))

if __name__ == '__main__':
    sys.exit(main())
