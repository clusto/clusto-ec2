from boto.ec2 import blockdevicemapping
from clusto.drivers.devices.servers import BasicVirtualServer
from clusto.exceptions import ResourceException
from clustoec2.drivers.resourcemanagers.ec2vmmanager import EC2VMManager
import IPy
from mako.template import Template
import time

MAX_POLL_COUNT = 30


class EC2VirtualServer(BasicVirtualServer):

    _driver_name = "ec2virtualserver"
    _i = None

    @property
    def _instance(self):
        """
        Returns a boto.ec2.Instance object to work with
        """

        if not self._i:
            res = EC2VMManager.resources(self)[0]
            vmman = EC2VMManager.get_resource_manager(res)

            c = vmman._connection(res.value['region'])
            instance_id = res.value['instance_id']
            rs = c.get_all_instances(instance_ids=[instance_id])
            self._i = rs[0].instances[0]
        return self._i

    @property
    def state(self):
        """
        Get the instance state
        """

        return self._instance.update()

    def console(self, *args, **kwargs):
        """
        Returns the console log output from the EC2 instance
        """
        console = self._instance.get_console_output()
        return console.output

    def get_ips(self, objects=False):
        """
        Returns a list of IP addresses to work with. Alternatively,
        it can return a list of IPy.IP objects.
        """
        ips = []
        l = self.attr_values(key='ip', subkey='nic-eth0')
        if l:
            if objects:
                [ips.append(IPy.IP(_)) for _ in l]
            else:
                [ips.append(IPy.IP(_).strNormal()) for _ in l]
        l = self.attr_values(key='ip', subkey='ext-eth0')
        if l:
            if objects:
                [ips.append(IPy.IP(_)) for _ in l]
            else:
                [ips.append(IPy.IP(_).strNormal()) for _ in l]
        return ips

    def update_metadata(self, *args, **kwargs):
        """
        Updates the IP attributes for this instance
        """

        self.clear_metadata()
        self._instance.update()
        if self._instance.private_ip_address:
            self.set_attr(
                key='ip',
                subkey='nic-eth0',
                value=IPy.IP(self._instance.private_ip_address).int()
            )
        if self._instance.ip_address:
            self.set_attr(
                key='ip',
                subkey='ext-eth0',
                value=IPy.IP(self._instance.ip_address).int()
            )

    def clear_metadata(self, *args, **kwargs):
        """
        Deletes the metadata that can change
        """
        self.del_attrs(key='ip')

    def power_off(self, captcha=True):
        if captcha and not self._power_captcha('shutdown'):
            return False
        self._instance.stop()

    def power_on(self, captcha=False):
        if captcha and not self._power_captcha('start'):
            return False
        self._instance.start()

    def power_reboot(self, captcha=True):
        if captcha and not self._power_captcha('reboot'):
            return False
        self._instance.reboot()

    def _build_user_data(self, udata=None):
        """
        Builds and returns a userdata string based on the
        user data string attribute
        """

        udata = self.attr_value(key='aws', subkey='ec2_user_data',
            merge_container_attrs=True)

        if udata:
            template = Template(udata)
            return template.render(
                clusto={
                    'name': self.name,
                    'region': self.attr_value(
                        key='aws',
                        subkey='ec2_region',
                        merge_container_attrs=True
                    ),
                }
            )
        else:
            return None

    def _ephemeral_storage(self):
        """
        Return the appropriate block mapping so you
        get your ephemeral storage drives
        """

#       Apparently amazon only gives you 4 ephemeral drives
        number = 4
        mapping = blockdevicemapping.BlockDeviceMapping()
        for block in range(0, number):
            eph = blockdevicemapping.BlockDeviceType()
            eph.ephemeral_name = 'ephemeral%d' % (block, )
            mapping['/dev/sd%s' % (chr(ord('b') + block),)] = eph
        return mapping

    def create(self, vmman, captcha=False, wait=True):
        """
        Creates an instance if it isn't already created
        """

        try:
            if self._instance:
                raise ResourceException('This instance is already created')
        except IndexError:
#           Instance doesn't exist, create
            pass
        except:
            raise

        image_id = self.attr_value(key='aws', subkey='ec2_ami',
            merge_container_attrs=True)

        if not image_id:
            raise ResourceException('No image specified for %s' %
                (self.name,))

        region = self.attr_value(key='aws', subkey='ec2_region',
            merge_container_attrs=True) or 'us-east-1'

        instance_type = self.attr_value(key='aws', subkey='ec2_instance_type',
            merge_container_attrs=True)

        if not instance_type:
            raise ResourceException('No instance type specified for %s' %
                (self.name,))

        placement = self.attr_value(key='aws', subkey='ec2_placement',
                                     merge_container_attrs=True)

        user_data = self._build_user_data()

        key_name = self.attr_value(key='aws', subkey='ec2_key_name',
            merge_container_attrs=True)

        security_groups = self.attr_values(
            key='aws',
            subkey='ec2_security_group',
            merge_container_attrs=True
        )

        image = vmman._connection(region).get_image(image_id)
#       Unless you explicitly skip the creation of ephemeral drives, these
#       will get created, you're already paying for them after all
        block_mapping = None
        if not self.attr_value(key='aws', subkey='ec2_skip_ephemeral',
            merge_container_attrs=True):
            block_mapping = self._ephemeral_storage()
        reservation = image.run(instance_type=instance_type,
            placement=placement,
            key_name=key_name,
            user_data=user_data,
            security_groups=security_groups,
            block_device_map=block_mapping)

        self._i = reservation.instances[0]
        self._i.add_tag('Name', self.name)
        result = vmman.allocate(self, resource=self._i)
        if wait:
            self.poll_until('running')

        return (result, True)

    def poll_until(self, state, interval=2, max_poll=MAX_POLL_COUNT):
        """
        Polls for the requested status, with a possible timeout.
        Shamelessly stolen from py-smartdc
        """

        c = 0
        while self.state != state and c < max_poll:
            c += 1
            time.sleep(interval)

    def poll_while(self, state, interval=2, max_poll=MAX_POLL_COUNT):
        """
        Polls whil the status doesn't change, with a possible timeout.
        Shamelessly stolen from py-smartdc
        """

        c = 0
        while self.state == state and c < max_poll:
            c += 1
            time.sleep(interval)

    def destroy(self, captcha=True, wait=True):
        """
        Destroys this instance if it exists
        """
        if captcha and not self._power_captcha('destroy'):
            return False

        try:
            if self._instance:
                pass
        except IndexError:
            raise ResourceException('This instance appears to be gone')
        except:
            raise

        instance_id = self._instance.id
        volumes = self._instance.connection.get_all_volumes(
            filters={'attachment.instance-id': instance_id})
        self._instance.terminate()
        if wait:
            self.poll_until('terminated')
#       destroy all volumes
        warnings = []
        for vol in volumes:
            dev = vol.attach_data.device.split('/')[-1]
#           if instance is terminated, delete everything
            if self.state == 'terminated':
                vol.delete()
            else:
#               It could be that some instances haven't freed their volumes
                try:
                    vol.delete()
                except Exception as e:
                    warnings.append("Couldn't delete volume %(dev)s (%(id)s) "
                        "from %(name)s, reason: %(reason)s" % {
                            'dev': dev,
                            'id': vol.id,
                            'name': self.name,
                            'reason': e.error_message
                        }
                    )

#       finally, delete the entity from clustometa
        self.entity.delete()
        return warnings

    def reconcile_ebs_volumes(self):
        """
        Will reflect the changes from amazon in clusto first,
        whatever's left from clusto to amazon
        """

        volumes = {}
        conn = self._instance.connection
#       Seems important to grab the placement from the instance data in the
#       unlikely scenario the clusto data doesn't match?
        zone = self._instance.placement
        instance_id = self._instance.id
        for attr in self.attrs(key='aws', merge_container_attrs=True):
            if not attr.subkey.startswith('ebs_'):
                continue
            volume = '_'.join(attr.subkey.split('_')[1:])
            if volume not in volumes.keys():
                volumes[volume] = {}
            try:
                volumes[volume]['size'] = int(attr.value)
            except ValueError:
                if attr.value.startswith('vol-'):
                    volumes[volume]['vol-id'] = attr.value
                else:
                    volumes[volume]['extra'] = attr.value

        for dev, data in volumes.items():
            device = '/dev/%s' % (dev, )
            vol = None
            if 'vol-id' not in data.keys():
#               create the volumes w/ default size of 10G
                vol = conn.create_volume(int(data['size']), zone)
                self.add_attr(key='aws',
                    subkey='ebs_%s' % (dev,), value=vol.id)
            else:
                try:
                    vol = conn.get_all_volumes(volume_ids=[data['vol-id']])
                    vol = vol[0]
                except:
#                   This volume does not exist anymore
                    self.del_attrs(key='aws', subkey='ebs_%s' % (dev,))
            if vol:
#               Attach the volume if it's not attached
                if not vol.attachment_state():
                    vol.attach(instance_id, device)
                else:
#                   Ok so it's attached, but what if it's attached to something
#                   else? if that is the case we should clear the attrs
                    try:
                        is_mine = conn.get_all_volumes(
                            volume_ids=[data['vol-id']],
                            filters={'attachment.instance-id': instance_id})
                    except:
                        is_mine = False
                    if is_mine:
                        vol.add_tag('Name', '%s:%s' % (self.name, device,))
                    else:
                        self.del_attrs(key='aws', subkey='ebs_%s' % (dev,))

#       Ok so now from aws to clusto
        volumes = conn.get_all_volumes(
            filters={'attachment.instance-id': instance_id})

        for vol in volumes:
            device = vol.attach_data.device
            dev = device.split('/')[-1]
#           update attrs that are not in our db
            if not self.attrs(key='aws', subkey='ebs_%s' % (dev,)):
                self.add_attr(key='aws', subkey='ebs_%s' % (dev,),
                    value=int(vol.size))
                self.add_attr(key='aws', subkey='ebs_%s' % (dev,),
                    value=vol.id)
            tag = '%s:%s' % (self.name, device)
            if 'Name' not in vol.tags or vol.tags['Name'] != tag:
                vol.add_tag('Name', tag)
