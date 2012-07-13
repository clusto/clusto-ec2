#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

import sys

import clusto
from clusto import script_helper
from clustoec2 import drivers as ec2_drivers


class BootstrapEc2(script_helper.Script):
    """
    Will bootstrap your ec2 infrastructure (regions, zones, etc)
    """

    def __init__(self):
        script_helper.Script.__init__(self)

    def _add_arguments(self, parser):
        parser.add_argument('--aws-key', '-k', required=True,
            help='Your Amazon web services key')
        parser.add_argument('--aws-secret-key', '-s', required=True,
            help='Your Amazon web services secret key')
        parser.add_argument('--vm-manager', '-m', default='ec2vmman',
            help='Name of the EC2 VM Manager you want to use/initialize')
        parser.add_argument('--ip-manager', '-i', default='ec2ipman',
            help='Name of the EC2 IP Manager you want to use/initialize')

    def add_subparser(self, subparsers):
        parser = self._setup_subparser(subparsers)
        self._add_arguments(parser)

    def run(self, args):
        self.debug('Grab or create the VM Manager')
        ec2vmman = clusto.get_entities(clusto_types=[ec2_drivers.EC2VMManager])
        if not ec2vmman:
            if not args.aws_key and not args.aws_secrets_key:
                raise Exception("you must specify both an aws_access_key_id "
                    "and an aws_secret_access_key if you don't already have "
                    "an EC2VMManager")
            ec2vmman = ec2_drivers.EC2VMManager(args.vm_manager,
                aws_access_key_id=args.aws_key,
                aws_secret_access_key=args.aws_secret_key)
            self.info('Created the "%s" EC2 VMManager' % (args.vm_manager))
        else:
            ec2vmman = ec2vmman.pop()

        self.debug('Grab or create the IP Manager')
        ec2ipman = clusto.get_entities(clusto_types=[ec2_drivers.EC2IPManager])
        if not ec2ipman:
            if not args.aws_key and not args.aws_secret_key:
                raise Exception("you must specify both an aws_access_key_id "
                    "and an aws_secret_access_key if you don't already have "
                    "an EC2IPManager")
            ec2ipman = ec2_drivers.EC2IPManager(args.ip_manager,
                aws_access_key_id=args.aws_key,
                aws_secret_access_key=args.aws_secret_key)
            self.info('Created the "%s" EC2 IPManager' % (args.ip_manager))
        else:
            ec2ipman = ec2ipman.pop()

        conn = ec2vmman._ec2_connection()

        self.info('Creating all available regions')
        for region in conn.get_all_regions():
            curconn = ec2vmman._ec2_connection(region.name)
            region_entity = clusto.get_or_create(region.name,
                ec2_drivers.EC2Region,
                region=region.name)
            self.debug('Created "%s" region' % (region.name, ))
#           Create all zones
            for zone in curconn.get_all_zones():
                zone_entity = clusto.get_or_create(zone.name,
                    ec2_drivers.EC2Zone,
                    placement=zone.name)
                self.debug('Created "%s" zone' % (zone.name, ))
                if zone_entity not in region_entity:
                    region_entity.insert(zone_entity)
                self.debug('Inserted "%s" zone in "%s" region' %
                    (zone.name, region.name, ))
        self.info('Finished, AWS objects should now be in the database')


def main():
    bootstrap, args = script_helper.init_arguments(BootstrapEc2)
    return(bootstrap.run(args))

if __name__ == '__main__':
    sys.exit(main())
