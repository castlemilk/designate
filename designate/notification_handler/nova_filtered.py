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
    name='handler:nova_filtered',
    title="Configuration for Nova Notification Handler"
))

cfg.CONF.register_opts([
    cfg.ListOpt('notification-topics', default=['notifications']),
    cfg.StrOpt('control-exchange', default='nova'),
    cfg.StrOpt('address-filter', default='*'),
    cfg.StrOpt('zone-id'),
    cfg.StrOpt('zone-name'),
    cfg.MultiStrOpt('formatv4'),
    cfg.MultiStrOpt('format', deprecated_for_removal=True,
                    deprecated_reason="Replaced by 'formatv4/formatv6'",
                    ),
    cfg.MultiStrOpt('formatv6')
], group='handler:nova_filtered')


class NovaFixedFilteredHandler(BaseAddressHandler):
    """Handler for Nova's notifications"""
    __plugin_name__ = 'nova_filtered'

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
        data = super(NovaFixedFilteredHandler, self)._get_ip_data(addr_dict)
        data['label'] = addr_dict['label']
        return data
    def get_filtered_addresses(self, addresses):
        """ Addresses is in format:
        fixed_ips = [{
            "floating_ips": [],
            "label": "private",
            "version": 4,
            "meta": {},
            "address": "172.16.0.14",
            "type": "fixed"
        }]
        """
        valid_address = lambda x: IP(x) in IP(cfg.CONF[self.name].address_filter)
        filtered_addresses = []
        for address in addresses:
            if valid_address(address.address):
                filtered_addresses.append(address)
        return filtered_addresses

    def process_notification(self, context, event_type, payload):
        LOG.debug('NovaFixedFilteredHandler received notification - %s', event_type)

        zone_id = cfg.CONF[self.name].zone_id
        if event_type == 'compute.instance.create.end':
            payload['project'] = getattr(context, 'tenant', None)
            filtered_addresses = get_filteredaddresses(payload['fixed_ips']) 
            if filtered_addresses:
                LOG.debug('NovaFixedFilteredHandler Filtered %d -> %d', len(payload['fixed_ips'], len(cfg.CONF[self.name].address_filter))
                self._create(addresses=filtered_addresses,
                         extra=payload,
                         zone_id=zone_id,
                         resource_id=payload['instance_id'],
                         resource_type='instance')
            else:
                LOG.debug('NovaFixedFilteredHandler No Results after filtering for %s', self.address_filter)

        elif event_type == 'compute.instance.delete.start':
            self._delete(zone_id=zone_id,
                         resource_id=payload['instance_id'],
                         resource_type='instance')
