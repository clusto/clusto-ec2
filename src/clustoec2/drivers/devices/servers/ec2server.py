from boto.ec2 import blockdevicemapping
from clusto.drivers.devices.servers import BasicVirtualServer
from clusto.exceptions import ResourceException
from clustoec2.drivers.resourcemanagers import ec2connmanager
from datetime import datetime
import IPy
from mako import template
import os
import time

MAX_POLL_COUNT = 30


class EC2VirtualServer(BasicVirtualServer):

    _driver_name = "ec2virtualserver"
    _i = None
    _int_ip_const = 2147483648

    def _int_to_ipy(self, num):
        return IPy.IP(num + self._int_ip_const)

    @property
    def _instance(self):
        """
        Returns a boto.ec2.Instance object to work with
        """

        if not self._i:
            instance_data = self.attr_value(key='ec2connmanager',
                subkey='instance')
            if not instance_data:
                return None
            instance_id = instance_data.get('instance_id')
            if not instance_id:
                return None
            res = ec2connmanager.EC2ConnectionManager.resources(self)[0]
            mgr = ec2connmanager.EC2ConnectionManager.get_resource_manager(res)
            c = mgr._connection(res.value['region'])
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

    @property
    def private_ips(self):
        """
        Only return private IP addresses
        """
        return self.get_ips(objects=True, private=True, public=False)

    @property
    def public_ips(self):
        """
        Only return public IP addresses
        """
        return self.get_ips(objects=True, private=False, public=True)

    def get_ips(self, objects=False, private=True, public=True):
        """
        Returns a list of IP addresses to work with. Alternatively,
        it can return a list of IPy.IP objects.
        """
        ips = []
        if private:
            l = self.attr_values(key='ip', subkey='nic-eth')
            if l:
                if objects:
                    [ips.append(self._int_to_ipy(_)) for _ in l]
                else:
                    [ips.append(self._int_to_ipy(_).strNormal()) for _ in l]
        if public:
            l = self.attr_values(key='ip', subkey='ext-eth')
            if l:
                if objects:
                    [ips.append(self._int_to_ipy(_)) for _ in l]
                else:
                    [ips.append(self._int_to_ipy(_).strNormal()) for _ in l]
        return ips

    def update_metadata(self, *args, **kwargs):
        """
        Updates the IP attributes for this instance
        """

        self.clear_metadata()
        self._instance.update()
        if self._instance.private_ip_address:
            self.add_attr(
                key='ip',
                subkey='nic-eth',
                value=IPy.IP(self._instance.private_ip_address).int() - \
                    self._int_ip_const
            )
        if self._instance.ip_address:
            self.add_attr(
                key='ip',
                subkey='ext-eth',
                value=IPy.IP(self._instance.ip_address).int() - \
                    self._int_ip_const
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
            tpl = template.Template(udata)
            attr_dict = {}
#           Add all aws information as values
            for attr in self.attrs(key='aws', merge_container_attrs=True):
                if not attr.subkey.startswith('ec2_'):
                    continue
#               don't recurse
                if attr.subkey == 'ec2_user_data':
                    continue
                k = '_'.join(attr.subkey.split('_')[1:])
                if k == 'boot_script':
                    if os.path.isfile(attr.value):
                        f = open(attr.value, 'rb')
                        attr_dict[k] = f.read()
                        f.close()
                else:
                    attr_dict[k] = attr.value
            attr_dict.update({'name': self.name,})
            return tpl.render(**attr_dict)
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

    def _get_or_create_security_groups(self, conn, ids=False):
        """
        If security groups don't exist, they will get created. Results will
        be returned to calling argument. It receives the current connection
        used as a parameter
        """

        subkey = 'ec2_security_group_id' if ids else 'ec2_security_group'
        filter_key = 'group-id' if ids else 'group-name'

        sgs = self.attr_values(
            key='aws',
            subkey=subkey,
            merge_container_attrs=True
        )
        sec_groups = []
        for sg in sgs:
            found = conn.get_all_security_groups(filters={filter_key: sg})
            if found:
                found[0] in sec_groups or sec_groups.append(found[0])
            else:
                desc = 'Created on %s' % (datetime.now(),)
                group = conn.create_security_group(name=sg, description=desc)
                sec_groups.append(group.name)

        return sec_groups


    def create(self, captcha=False, wait=True):
        """
        Creates an instance if it isn't already created
        """

        try:
            if self._instance:
                raise ResourceException('This instance is already created')
        except:
            raise

        res = ec2connmanager.EC2ConnectionManager.resources(self)[0]
        mgr = ec2connmanager.EC2ConnectionManager.get_resource_manager(res)

#       We build these on a different step
        skip_attrs = ['ec2_security_group', 'ec2_security_group_id', 'ec2_user_data']

#       Grab all the `ec2_*` attributes available
        ec2_attrs = dict([(_.subkey, _.value) for _ in self.attrs(key='aws', \
                    merge_container_attrs=True) if _.subkey and \
                    _.subkey.startswith('ec2_') and _.subkey \
                    not in skip_attrs])

        image_id = ec2_attrs.pop('ec2_ami', None)
        if not image_id:
            raise ResourceException('No image specified for %s' %
                (self.name,))

        region = ec2_attrs.pop('ec2_region', 'us-east-1')

        instance_type = ec2_attrs.pop('ec2_instance_type', None)
        if not instance_type:
            raise ResourceException('No instance type specified for %s' %
                (self.name,))

        placement = ec2_attrs.pop('ec2_placement', None)
        user_data = self._build_user_data()
        key_name = ec2_attrs.pop('ec2_key_name', None)

        image = mgr._connection(region).get_image(image_id)
#       Unless you explicitly skip the creation of ephemeral drives, these
#       will get created, you're already paying for them after all
        block_mapping = None
        skip_ephemeral = ec2_attrs.pop('ec2_skip_ephemeral', False)
        if not skip_ephemeral:
            block_mapping = self._ephemeral_storage()

#       Now we need to check if this is vpc or not
        is_vpc = self.attr_value(key='aws', subkey='is_vpc', merge_container_attrs=True)

        extra_args = dict(('_'.join(_.split('_')[1:]), __) \
                     for _,__ in ec2_attrs.items())

        if is_vpc:
            security_group_ids = self._get_or_create_security_groups(
                                    mgr._connection(region), ids=True)
            extra_args['security_group_ids'] = security_group_ids
        else:
            security_groups = self._get_or_create_security_groups(
                                    mgr._connection(region))
            extra_args['security_groups'] = security_groups

        reservation = image.run(instance_type=instance_type,
            placement=placement,
            key_name=key_name,
            user_data=user_data,
            block_device_map=block_mapping,
            **extra_args)

        self._i = reservation.instances[0]
        self._i.add_tag('Name', self.name)
        result = mgr.additional_attrs(self, resource={'instance': self._i})
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
#           It could be that some instances haven't freed their volumes
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
