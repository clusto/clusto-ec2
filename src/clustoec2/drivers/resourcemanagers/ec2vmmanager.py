from boto import ec2
from clusto.drivers.base import ResourceManager
from clusto.exceptions import ResourceException
import time


class EC2VMManagerException(ResourceException):
    pass


class EC2VMManager(ResourceManager):

    _driver_name = 'ec2vmmanager'
    _attr_name = 'ec2vmmanager'

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

    def _image_to_dict(self, image):
        """
        Returns a dictionary with AMI information
        """
        return {
            'region': image.region.name,
            'image_id': image.id,
        }

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

    def get_all_ec2_instance_resources(self, regions=[]):
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

    def allocate(self, thing, resource=(), number=True):
        """
        Makes sure allocate works with only EC2 Instance objects
        """
        if resource == ():
            return super(EC2VMManager, self).allocate(thing,
                resource=resource, number=number)
        else:
            if not isinstance(resource, ec2.instance.Instance):
                raise TypeError('You can only allocate EC2 image resources')
            r = self._instance_to_dict(resource)
            return super(EC2VMManager, self).allocate(thing,
                resource=r, number=number)

    def allocator(self, thing, resource=(), number=True):
        """
        This should only be called if you expect a new instance to be
        allocated without .create()
        """
        raise EC2VMManagerException('EC2VMManager cannot allocate on its own,'
            ' needs to be called via .create()')
