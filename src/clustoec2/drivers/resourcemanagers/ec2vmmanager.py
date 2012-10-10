import boto
from boto.ec2 import blockdevicemapping
from clusto.drivers.base import ResourceManager
from clusto.exceptions import ResourceException
from mako.template import Template
import time


class EC2VMManagerException(ResourceException):
    pass


class EC2VMManager(ResourceManager):

    _driver_name = 'ec2vmmanager'
    _attr_name = 'ec2vmmanager'

    _conn = None
    _properties = {'aws_access_key_id': None,
                   'aws_secret_access_key': None}

    @property
    def _connection(self, region=None):
        if not self._conn:
            if not region or region == 'us-east-1':
                self._conn = boto.connect_ec2(
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key
                )
            else:
                self._conn = boto.ec2.connect_to_region(
                    region,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key
                )
        return self._conn

    def _instance_to_dict(self, instance):

        return {
            'placement': instance.placement,
            'instance_id': instance.id,
        }

    def _create_ephemeral_storage(self):
#       Apparently amazon only gives you 4 ephemeral drives
        number = 4
        mapping = blockdevicemapping.BlockDeviceMapping()
        for block in range(0, number):
            eph = blockdevicemapping.BlockDeviceType()
            eph.ephemeral_name = 'ephemeral%d' % (block, )
            mapping['/dev/sd%s' % (chr(ord('b') + block),)] = eph
        return mapping

    def _get_instance_from_resource(self, resource):

        conn = self._connection(resource['placement'][:-1])

        il = conn.get_all_instances(instance_ids=[resource['instance_id']])

        return il[0].instances[0]

    def _stop_instance(self, resource):

        conn = self._connection(resource['placement'][:-1])

        try:
            reservations = conn.get_all_instances([resource['instance_id']])
        except boto.exception.EC2ResponseError, ex:
            if ex.error_code == 'InvalidInstanceID.NotFound':
                return

        for reservation in reservations:
            for instance in reservation.instances:
                if instance.id == resource['instance_id']:
                    instance.stop()
                    return

    def get_all_ec2_instance_resources(self):
        """Query AWS and return all active ec2 instances and their state"""

        instance_resources = []

        regions = [r.name for r in self._connection().get_all_regions()]

        for region in regions:

            conn = self._connection(region)

            for reservation in conn.get_all_instances():
                for instance in reservation.instances:
                    instance_resources.append({
                        'resource': self._instance_to_dict(instance),
                        'state': instance.state
                    })

        return instance_resources

    def additional_attrs(self, thing, resource, number):

        for name, val in resource.items():
            self.set_resource_attr(thing,
                                   resource,
                                   number=number,
                                   key=str(name),
                                   value=str(val))

    def _build_user_data(self, thing):

        udata = thing.attr_value(key='aws', subkey='ec2_user_data',
                                 merge_container_attrs=True)

        if udata:
            template = Template(udata)
            return template.render(
                clusto={
                    'name': thing.name,
                    'region': thing.attr_value(
                        key='aws',
                        subkey='ec2_region',
                        merge_container_attrs=True
                    ),
                }
            )
        else:
            return None

    def allocator(self, thing):
        """
        Allocate VMs on ec2 while keeping track of
        current costs and staying within the budget

        """

        for res in self.resources(thing):
            raise ResourceException('%s is already assigned to %s' %
                (thing.name, res.value))

        region = thing.attr_value(key='aws', subkey='ec2_region',
                                  merge_container_attrs=True) or 'us-east-1'

        instance_type = thing.attr_value(key='aws', subkey='ec2_instance_type',
                                         merge_container_attrs=True)

        if not instance_type:
            raise ResourceException('No instance type specified for %s'
                                    % (thing.name,))

        image_id = thing.attr_value(key='aws', subkey='ec2_ami',
                                    merge_container_attrs=True)

        if not image_id:
            raise ResourceException('No AMI specified for %s' % (thing.name,))

        placement = thing.attr_value(key='aws', subkey='ec2_placement',
                                     merge_container_attrs=True)

        user_data = self._build_user_data(thing)

        key_name = thing.attr_value(key='aws', subkey='ec2_key_name',
                                    merge_container_attrs=True)

        security_groups = thing.attr_values(
            key='aws',
            subkey='ec2_security_group',
            merge_container_attrs=True
        )

        res = self.resources(thing)
        if len(res) > 1:
            raise ResourceException('%s is somehow already assigned more '
                'than one instance')
        elif len(res) == 1:
            raise ResourceException('%s is already running as %s'
                                    % (res[0].value,)
        else:
            c = self._connection(region)
            image = c.get_image(image_id)
#           Unless you explicitly skip the creation of ephemeral drives, these
#           will get created, you're already paying for them after all
            block_mapping = None
            if not thing.attr_value(key='aws', subkey='ec2_skip_ephemeral',
                merge_container_attrs=True):
                block_mapping = self._create_ephemeral_storage()
            reservation = image.run(instance_type=instance_type,
                placement=placement,
                key_name=key_name,
                user_data=user_data,
                security_groups=security_groups,
                block_device_map=block_mapping)

            i = reservation.instances[0]
            count = 0
            while True:
                state = i.update()
                if state != 'running' and count < 5:
                    print ('Instance still in the "%s" state, waiting '
                        '5 more seconds...' % (state,))
                    count = count + 1
                    time.sleep(5)
                else:
                    break
            i.add_tag('Name', thing.name)

        return (self._instance_to_dict(i), True)

    def deallocate(self, thing, resource=(), number=True,
        captcha=True, wait=True):
        """deallocates a resource from the given thing."""

        if thing.attr_value(key='aws', subkey='ec2_allow_termination',
                            merge_container_attrs=True) == False:
            raise EC2VMManagerException('Not Allowed to terminate %s.' %
                (thing.name,))

        if not resource:
            for resource in self.resources(thing):
                if thing.destroy(captcha, wait):
                    super(EC2VMManager, self).deallocate(
                        thing, resource.value, number)
                    thing.clear_metadata()
                    thing.entity.delete()
                    return True
                else:
                    return False
        else:
            return super(EC2VMManager, self).deallocate(
                thing, resource.value, number)
