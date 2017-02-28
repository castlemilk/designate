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
    name='handler:nova_fixed_filtered',
    title="Configuration for Nova Notification Handler WITH FILTERING"
))
cfg.CONF.register_opts([
    cfg.ListOpt('notification-topics', default=['notifications']),
    cfg.StrOpt('control-exchange', default='nova'),
    cfg.StrOpt('address-filter', default='0.0.0.0/0'),
    cfg.StrOpt('zone-id'),
    cfg.MultiStrOpt('formatv4'),
    cfg.MultiStrOpt('format', deprecated_for_removal=True,
                    deprecated_reason="Replaced by 'formatv4/formatv6'",
                    ),
    cfg.MultiStrOpt('formatv6')
], group='handler:nova_fixed_filtered')


class NovaFixedFilterHandler(BaseAddressHandler):
    """Handler for Nova's notifications WITH FILTERING"""
    __plugin_name__ = 'nova_fixed_filtered'

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
        data = super(NovaFixedFilterHandler, self)._get_ip_data(addr_dict)
        data['label'] = addr_dict['label']
        return data

    def process_notification(self, context, event_type, payload):
        LOG.debug('NovaFixedFilterHandler received notification - %s', event_type)

        zone_id = cfg.CONF[self.name].zone_id
        if event_type == 'compute.instance.create.end':
            payload['project'] = getattr(context, 'tenant', None)
            valid_address = lambda x: IP(x) in IP(cfg.CONF[self.name].address_filter)
            filtered_addresses = []
            for address in payload['fixed_ips']:
                LOG.debug('NovaFixedFilterHandler:address:%s', address['address'])
                if valid_address(address['address']):
                    LOG.debug('NovaFixedFilterHandler:address:valid:True')
                    filtered_addresses.append(address) 
            if filtered_addresses:
                self._create(addresses=filtered_addresses,
                         extra=payload,
                         zone_id=zone_id,
                         resource_id=payload['instance_id'],
                         resource_type='instance')

        elif event_type == 'compute.instance.delete.start':
            self._delete(zone_id=zone_id,
                         resource_id=payload['instance_id'],
                         resource_type='instance')
