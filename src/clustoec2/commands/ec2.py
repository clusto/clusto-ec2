#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

import os
import pprint
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

import clusto
from clusto import script_helper
from clustoec2 import drivers as ec2_drivers


class Ec2(script_helper.Script):

    _instance_driver = ec2_drivers.servers.EC2VirtualServer
    _default_conn_manager = 'ec2connman'

    def __init__(self, *args, **kwargs):
        script_helper.Script.__init__(self, *args, **kwargs)
        self.formatters = {
            'pprint': (
                pprint.pformat, {'indent': 4},
            )
        }
        if YAML:
            self.formatters['yaml'] = (
                yaml.safe_dump,
                {
                    'encoding': 'utf-8',
                    'explicit_start': True,
                    'default_flow_style': False,
                },
            )
        if JSON:
            self.formatters['json'] = (
                json.dumps,
                {
                    'indent': 2,
                    'sort_keys': True
                }
            )

    def run(self, args):
        "Main run method"

        objects = []
        for _ in args.instances:
            try:
                objects.append(clusto.get_by_name(_))
            except LookupError:
                self.warn('Could not find instance %s in the clusto database' % (_,))
                if args.command == 'create':
                    self.info('Creating clusto object for %s' % (_,))
                    objects.append(self._instance_driver(_))
            except Exception as e:
                self.critical(e)
                return
        kwargs = dict(args.__dict__.items())
        for _ in ('command', 'config', 'dsn', 'loglevel', 'instances',):
            kwargs.pop(_)
        kwargs['objects'] = objects
        self.debug(kwargs)
        # Only the create command should (and in fact, *must*) receive an empty list of objects
        if not objects:
            self.error('Cannot run with an empty list of instances')
            return 1
        return (getattr(self, 'run_%s' % (args.command, ))(**kwargs))

    def _get_instance_data(self, instance):
        """
        Returns AWS data given an instance
        """
        connman = instance.attr_value(key='awsconnection', subkey='manager')
        data = connman._instance_to_dict(instance._instance)
        return data

    def run_show(self, **kwargs):
        "Prints the AWS data of the given objects to stdout"

        objs = []
        for obj in kwargs.get('objects'):
            objs.append({obj.name: self._get_instance_data(obj)})
        self.debug(objs)
        cb = self.formatters[kwargs.get('format', 'pprint')]
        print cb[0](objs, **cb[1])

    def run_state(self, **kwargs):
        "Prints the AWS state of the given objects to stdout"

        objs = []
        for obj in kwargs.get('objects'):
            objs.append({obj.name: obj.state})
        self.debug(objs)
        cb = self.formatters[kwargs.get('format', 'pprint')]
        print cb[0](objs, **cb[1])

    def _change_state(self, **kwargs):
        "Handles changing the state to running/stopped"

        state = kwargs['state']
        assert state in ('running', 'stopped',)
        wait = kwargs.get('wait', False)
        objs = kwargs.get('objects', [])
        confirm = False
        self.debug(objs)
        for obj in objs:
            self.info('Changing %s to %s state' % (obj.name, state, ))
            if state == 'running':
                confirm = obj.power_on()
            elif state == 'stopped':
                confirm = obj.power_off()
            else:
                pass
        # If waiting, only wait for the last one to change state
        if confirm and wait:
            self.info('Wait until instance(s) is/are in %s state' % (state,))
            obj.poll_until(state)

    def run_start(self, **kwargs):
        "Marshall over to _change_state"
        return self._change_state(state='running', **kwargs)

    def run_stop(self, **kwargs):
        "Marshall over to _change_state"
        return self._change_state(state='stopped', **kwargs)

    def run_create(self, **kwargs):
        "Create one or more EC2 instance(s) (if not exist)"
        objs = kwargs.get('objects', [])
        for obj in objs:
            try:
                self.info('Attempting to create %s' % (obj.name,))
                obj.create()
            except Exception as e:
                self.error('Error creating %s: %s' % (obj.name, e,))
        self.info('All objects created')
        return

    def _add_common_arguments(self, parser):
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
            '--conn-manager', '-c', default=self._default_conn_manager,
            help='Name of the EC2 Connection Manager you want to use'
        )
        formats = ['pprint']
        if YAML:
            formats.append('yaml')
        if JSON:
            formats.append('json')
        cmds = (
            'state',
            'show',
            'start',
            'stop',
            'create',
        )
        parser.add_argument(
            '-f', '--format', choices=formats, default='pprint',
            help='Default format to present results in'
        )
        parser.add_argument(
            '--wait', action='store_true', default=False,
            help='Wait for interaction with instances to finish (start/stop/create/destroy)'
        )
        parser.add_argument(
            '-p', '--pool', action='append', default=[],
            help='Add this instance to these pools before creating'
        )
        parser.add_argument(
            '-sg', '--security-group', action='append', default=[],
            help='Add new instance(s) to security group(s) (for create only). '
            'Keep in mind that security groups will be created if they don\'t exist'
        )
        parser.add_argument(
            'command', choices=cmds,
            help='EC2 command to run'
        )
        parser.add_argument(
            'instances', nargs='+', metavar='instance',
            help='EC2 instance(s) to interact with'
        )

    def _add_arguments(self, parser):
        self._add_common_arguments(parser)


def main():
    ec2, args = script_helper.init_arguments(Ec2)
    return(ec2.run(args))

if __name__ == '__main__':
    sys.exit(main())
