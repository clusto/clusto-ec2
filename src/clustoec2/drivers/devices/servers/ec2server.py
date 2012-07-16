
from clusto.drivers.devices.common import IPMixin
from clusto.drivers.devices.servers import BasicVirtualServer
from clustoec2.drivers.resourcemanagers.ec2vmmanager import EC2VMManager

import time

class EC2VirtualServer(BasicVirtualServer, IPMixin):
    _driver_name = "ec2virtualserver"

    _port_meta = {}


    @property
    def _instance(self):
        res = EC2VMManager.resources(self)[0]
        manager = EC2VMManager.get_resource_manager(res)

        instance = manager._get_instance_from_resource(res.value)
        return instance

    def get_state(self):
        """Get the instance state."""

        return self._instance.state

    def console(self, *args, **kwargs):

        console = self._instance.get_console_output()

        return console.output


    def update_metadata(self, *args, **kwargs):

        while True:

            state = self.get_state()


            if state == 'running':
                self.clear_metadata()
                self.bind_ip_to_osport(self._instance.private_ip_address,
                                       'nic-eth0')

                self.bind_ip_to_osport(self._instance.ip_address, 'ext-eth0')
                break

            if not kwargs.get('wait', False):
                break

            time.sleep(2)

    def clear_metadata(self, *args, **kwargs):
        self.del_attrs('ip')

    def shutdown(self, captcha=True):
        if captcha and not self._power_captcha('shutdown'):
            return False
        self._instance.stop()

    def start(self, captcha=True):
        if captcha and not self._power_captcha('start'):
            return False
        self._instance.start()

    def reboot(self, captcha=True):
        if captcha and not self._power_captcha('reboot'):
            return False
        self._instance.reboot()

    def destroy(self, captcha=True):
        if captcha and not self._power_captcha('destroy'):
            return False
        instance_id = self._instance.id
        volumes = self._instance.connection.get_all_volumes(
            filters={'attachment.instance-id': instance_id})
        self._instance.terminate()
        while True:
            state = self._instance.update()
            if state != 'terminated':
                print ('Instance still in the "%s" state, waiting '
                    '5 more seconds...' % (state,))
                time.sleep(5)
            else:
                break
#       destroy all volumes
        for vol in volumes:
            dev = vol.attach_data.device.split('/')[-1]
#           root device (sda1) will disappear along with the instance
            if dev != 'sda1':
                vol.delete()

        return True

    def reconcile_ebs_volumes(self):
        volumes = {}
        conn = self._instance.connection
#       Seems important to grab the placement from the instance data in the
#       unlikely scenario the clusto data doesn't match?
        zone = self._instance.placement
        instance_id = self._instance.id
        for attr in self.attrs(key='ebs', merge_container_attrs=True):
            if attr.subkey not in volumes.keys():
                volumes[attr.subkey] = {}
            try:
                volumes[attr.subkey]['size'] = int(attr.value)
            except ValueError:
                if attr.value.startswith('vol-'):
                    volumes[attr.subkey]['vol-id'] = attr.value
                else:
                    volumes[attr.subkey]['extra'] = attr.value

        for dev, data in volumes.items():
            device = '/dev/%s' % (dev, )
            vol = None
            if 'vol-id' not in data.keys():
#               create the volumes w/ default size of 10G
                vol = conn.create_volume(int(data['size']), zone)
                self.add_attr(key='ebs', subkey=dev, value=vol.id)
            else:
                try:
                    vol = conn.get_all_volumes(volume_ids=[data['vol-id']])
                    vol = vol[0]
                except:
#                   This volume does not exist anymore
                    self.del_attrs(key='ebs', subkey=dev)
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
                        self.del_attrs(key='ebs', subkey=dev)

#       Ok so now from aws to clusto
        volumes = conn.get_all_volumes(
            filters={'attachment.instance-id': instance_id})

        for vol in volumes:
            device = vol.attach_data.device
            dev = device.split('/')[-1]
#           update attrs that are not in our db
            if not self.attrs(key='ebs', subkey=dev):
                self.add_attr(key='ebs', subkey=dev, value=int(vol.size))
                self.add_attr(key='ebs', subkey=dev, value=vol.id)
            tag = '%s:%s' % (self.name, device)
            if 'Name' not in vol.tags or vol.tags['Name'] != tag:
                vol.add_tag('Name', tag)

