# Copyright 2012 Managed I.T.
#
# Author: Kiall Mac Innes <kiall@managedit.ie>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from oslo_config import cfg
from oslo_log import log as logging
from IPy import IP

from designate.notification_handler.base import BaseAddressHandler


LOG = logging.getLogger(__name__)

cfg.CONF.register_group(cfg.OptGroup(
    name='handler:nova_filter_map',
    title="Configuration for Nova Notification Handler WITH MAPPED FILTERING"
))
cfg.CONF.register_opts([
    cfg.ListOpt('notification-topics', default=['notifications']),
    cfg.ListOpt('zone_items'),
    cfg.StrOpt('control-exchange', default='nova'),
    cfg.MultiStrOpt('formatv4'),
    cfg.MultiStrOpt('format', deprecated_for_removal=True,
                    deprecated_reason="Replaced by 'formatv4/formatv6'",
                    ),
    cfg.MultiStrOpt('formatv6')
], group='handler:nova_filter_map')


class NovaFilterMapHandler(BaseAddressHandler):
    """Handler for Nova's notifications WITH MAPPED FILTERING"""
    __plugin_name__ = 'nova_filter_map'

    def get_exchange_topics(self):
        exchange = cfg.CONF[self.name].control_exchange

        topics = [topic for topic in cfg.CONF[self.name].notification_topics]

        return (exchange, topics)

    def get_event_types(self):
        return [
            'compute.instance.create.end',
            'compute.instance.delete.start',
        ]

    def _get_ip_data(self, addr_dict):
        data = super(NovaFilterMapHandler, self)._get_ip_data(addr_dict)
        data['label'] = addr_dict['label']
        return data

    def process_notification(self, context, event_type, payload):
        """
        Assume we have an item list: zone_id:zone_name:address_filter, ...
        i.e 13413525-242424-23423424:example.com:192.168.0.0/24, ...
        """
        LOG.debug('NovaFilterMapHandler received notification - %s', event_type)
        valid_address = lambda x, y: IP(x) in IP(y)
        map_items = cfg.CONF[self.name].zone_items
        zone_map = map(lambda x: {'zone_id': x[0], 'zone_name': x[1], 'address_filter': x[2]}, [x.strip().split(':') for x in map_items])
        if event_type == 'compute.instance.create.end':
            payload['project'] = getattr(context, 'tenant', None)
            for zone in zone_map:
                for address in payload['fixed_ips']:
                    LOG.debug('NovaFilterMapHandler:address_filter:%s', zone['address_filter'])
                    LOG.debug('NovaFilterMapHandler:address:%s', address['address'])
                    if valid_address(address['address'], zone['address_filter']):
                        LOG.debug('NovaFilterMapHandler:address:valid:True')
                        LOG.debug('NovaFilterMapHandler:address:adding to domain:%s', zone['zone_name'])
                        self._create(addresses=[address],
                                     extra=payload,
                                     zone_id=zone['zone_id'],
                                     resource_id=payload['instance_id'],
                                     resource_type='instance')

        elif event_type == 'compute.instance.delete.start':
            for zone in zone_map:
                self._delete(zone_id=zone['zone_id'],
                         resource_id=payload['instance_id'],
                         resource_type='instance')
