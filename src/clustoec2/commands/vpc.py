#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

import sys

JSON = False
YAML = False
try:
    import yaml
    assert yaml
    YAML = True
except ImportError:
    pass

try:
    import simplejson as json
    assert json
    JSON = True
except ImportError:
    try:
        import json
        assert json
        JSON = True
    except:
        pass

from clusto import script_helper
from clustoec2 import drivers as ec2_drivers
from clustoec2.commands import ec2


class Vpc(ec2.Ec2):

    _instance_driver = ec2_drivers.servers.VPCVirtualServer
    _default_conn_manager = 'vpcconnman'

    def _add_arguments(self, parser):
        self._add_common_arguments(parser)
        parser.add_argument(
            '-si', '--subnet-id', required=True,
            help='VPC Subnet ID you wish to create this VPC instance in'
        )


def main():
    ec2, args = script_helper.init_arguments(Vpc)
    return(ec2.run(args))

if __name__ == '__main__':
    sys.exit(main())
