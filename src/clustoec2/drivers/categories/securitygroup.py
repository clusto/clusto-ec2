#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#


from clusto.drivers import pool


class EC2SecurityGroup(pool.Pool):

    _driver_name = 'ec2_security_group'

    def __init__(self, name_driver_entity, **kwargs):
        pool.Pool.__init__(self, name_driver_entity, **kwargs)
        if 'group_id' in kwargs:
            self.set_attr(key='aws', subkey='ec2_security_group_id', value=kwargs.get('group_id'))
        if 'group_name' in kwargs:
            self.set_attr(key='aws', subkey='ec2_security_group', value=kwargs.get('group_name'))
